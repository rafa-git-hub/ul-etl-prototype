# etl/pipeline.py
# Главный ETL-пайплайн (Вопрос 1).
# Запуск:
#   DYLD_LIBRARY_PATH="/opt/homebrew/opt/libpq/lib" python3 etl/pipeline.py --start 2026-10-01 --end 2026-10-26

import argparse
import logging
import sys
from datetime import date

from connection import get_connection
from dq_rules import validate_price_row
from currency import (
    convert_to_rub,
    load_exchange_rates,
    get_rate,
    FOREIGN_CURRENCIES,
)
from categories import (
    calc_weight_category,
    calc_volume_category,
    body_group_from_price_body_types,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("etl")


def parse_args():
    parser = argparse.ArgumentParser(description="ETL: public.prices → core.prices_clean")
    parser.add_argument("--start", required=True, help="Дата начала (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="Дата окончания (YYYY-MM-DD)")
    return parser.parse_args()


def load_city_gcids(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SELECT DISTINCT gc_id FROM cities")
        return {row[0] for row in cur.fetchall()}


def load_body_types_by_price(conn, price_ids: list) -> dict:
    if not price_ids:
        return {}
    result = {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT price_id, body_type_id FROM price_body_types WHERE price_id = ANY(%s)",
            (price_ids,),
        )
        for price_id, body_type_id in cur.fetchall():
            result.setdefault(price_id, []).append(body_type_id)
    return result


def fetch_prices(conn, start_date: date, end_date: date) -> list:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, loading_date, loading_city_gcid, unloading_city_gcid,
                   distance, total_weight, total_volume, body_type,
                   price, currency_code, nearest_rate_date,
                   outlier_mark, organization_id, price_type
            FROM prices
            WHERE loading_date BETWEEN %s AND %s
              AND is_fact = true
              AND complex = false
            ORDER BY id
            """,
            (start_date, end_date),
        )
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def build_clean_row(row: dict, city_gcids: set, rates: dict, body_types_map: dict) -> dict:
    rate = get_rate(rates, row["currency_code"], row["nearest_rate_date"])
    price_rub = convert_to_rub(row["price"], row["currency_code"], rate)

    weight_cat = row.get("weight_category") or calc_weight_category(row["total_weight"])
    volume_cat = row.get("volume_category") or calc_volume_category(row["total_volume"])

    body_ids = body_types_map.get(row["id"], [])
    body_group = body_group_from_price_body_types(body_ids, row["body_type"])

    return {
        "source_price_id": row["id"],
        "loading_date": row["loading_date"],
        "loading_city_gcid": row["loading_city_gcid"],
        "unloading_city_gcid": row["unloading_city_gcid"],
        "distance": row["distance"],
        "total_weight": row["total_weight"],
        "total_volume": row["total_volume"],
        "body_group": body_group,
        "price_original": row["price"],
        "currency_code": row["currency_code"],
        "price_rub": price_rub,
        "weight_category": weight_cat,
        "volume_category": volume_cat,
        "outlier_mark": row["outlier_mark"],
        "organization_id": row["organization_id"],
        "price_type": row["price_type"],
    }


def upsert_clean_rows(conn, rows: list) -> int:
    if not rows:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO core.prices_clean (
                source_price_id, loading_date, loading_city_gcid, unloading_city_gcid,
                distance, total_weight, total_volume, body_group,
                price_original, currency_code, price_rub,
                weight_category, volume_category, outlier_mark,
                organization_id, price_type
            ) VALUES (
                %(source_price_id)s, %(loading_date)s, %(loading_city_gcid)s, %(unloading_city_gcid)s,
                %(distance)s, %(total_weight)s, %(total_volume)s, %(body_group)s,
                %(price_original)s, %(currency_code)s, %(price_rub)s,
                %(weight_category)s, %(volume_category)s, %(outlier_mark)s,
                %(organization_id)s, %(price_type)s
            )
            ON CONFLICT (source_price_id) DO UPDATE SET
                loading_date = EXCLUDED.loading_date,
                loading_city_gcid = EXCLUDED.loading_city_gcid,
                unloading_city_gcid = EXCLUDED.unloading_city_gcid,
                distance = EXCLUDED.distance,
                total_weight = EXCLUDED.total_weight,
                total_volume = EXCLUDED.total_volume,
                body_group = EXCLUDED.body_group,
                price_original = EXCLUDED.price_original,
                currency_code = EXCLUDED.currency_code,
                price_rub = EXCLUDED.price_rub,
                weight_category = EXCLUDED.weight_category,
                volume_category = EXCLUDED.volume_category,
                outlier_mark = EXCLUDED.outlier_mark,
                organization_id = EXCLUDED.organization_id,
                price_type = EXCLUDED.price_type,
                etl_loaded_at = now()
            """,
            rows,
        )
        return len(rows)


def insert_quarantine(conn, items: list) -> int:
    if not items:
        return 0
    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO core.dq_quarantine_prices (source_price_id, reason_code, details)
            VALUES (%(source_price_id)s, %(reason_code)s, %(details)s)
            ON CONFLICT (source_price_id, reason_code) DO NOTHING
            """,
            items,
        )
        return len(items)


def main():
    args = parse_args()
    start_date = date.fromisoformat(args.start)
    end_date = date.fromisoformat(args.end)

    log.info("ETL старт: %s — %s", start_date, end_date)

    with get_connection() as conn:
        log.info("Загружаю справочники...")
        city_gcids = load_city_gcids(conn)
        rates = load_exchange_rates(conn)
        log.info("Городов: %d, курсов: %d", len(city_gcids), len(rates))

        log.info("Читаю public.prices...")
        prices = fetch_prices(conn, start_date, end_date)
        log.info("Прочитано строк: %d", len(prices))
        if not prices:
            log.info("Нет данных за окно. Выход.")
            return

        price_ids = [p["id"] for p in prices]
        body_types_map = load_body_types_by_price(conn, price_ids)

        clean_rows = []
        quarantine_items = []
        for row in prices:
            dq = validate_price_row(row, city_gcids)
            if dq.is_valid:
                rate = get_rate(rates, row["currency_code"], row["nearest_rate_date"])
                if row["currency_code"] in FOREIGN_CURRENCIES and (
                        rate is None or convert_to_rub(row["price"], row["currency_code"], rate) is None
                ):
                    quarantine_items.append({
                        "source_price_id": row["id"],
                        "reason_code": "CURRENCY_RATE_MISSING",
                        "details": f"currency={row['currency_code']}, rate not found for {row['nearest_rate_date']}",
                    })
                    continue
                clean_rows.append(build_clean_row(row, city_gcids, rates, body_types_map))
            else:
                quarantine_items.append({
                    "source_price_id": row["id"],
                    "reason_code": dq.reason_code,
                    "details": dq.details,
                })

        log.info("Валидных: %d, в карантин: %d", len(clean_rows), len(quarantine_items))

        log.info("Пишу в core.prices_clean (UPSERT)...")
        upsert_clean_rows(conn, clean_rows)
        log.info("Пишу в core.dq_quarantine_prices (INSERT)...")
        insert_quarantine(conn, quarantine_items)

        conn.commit()
        log.info("ETL завершён.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log.error("ETL упал: %s", e, exc_info=True)
        sys.exit(1)