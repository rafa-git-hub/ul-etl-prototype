import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))
import math
import pandas as pd
from connection import get_connection


def extract_region(full_name_local: str) -> str:
    """'Казань, Республика Татарстан' → 'Республика Татарстан'."""
    if not full_name_local:
        return "unknown"
    parts = full_name_local.split(",", 1)
    return parts[1].strip() if len(parts) > 1 else "unknown"


def load_cities(conn) -> pd.DataFrame:
    """Дедуплицированный справочник городов (MIN(id) на gc_id)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (gc_id)
                gc_id, name, full_name_local, latitude, longitude
            FROM cities
            ORDER BY gc_id, id
        """)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def load_prices(conn, as_of: str, include_future: bool = False) -> pd.DataFrame:
    """Все факты из core.prices_clean. Если include_future — берём и будущие."""
    where = "loading_date <= %s" if not include_future else "1=1"
    params = (as_of,) if not include_future else ()
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT source_price_id, loading_date, loading_city_gcid, unloading_city_gcid,
                   distance, total_weight, total_volume, body_group,
                   weight_category, volume_category, price_rub,
                   organization_id, price_type
            FROM core.prices_clean
            WHERE {where}
        """, params)
        cols = [d[0] for d in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)


def build_features(prices: pd.DataFrame, cities: pd.DataFrame) -> pd.DataFrame:
    """Собирает признаки: гео, время, параметры груза."""
    # Гео: регионы + координаты
    cities_small = cities[["gc_id", "full_name_local", "latitude", "longitude"]].copy()
    cities_small["region"] = cities_small["full_name_local"].apply(extract_region)

    df = prices.merge(
        cities_small.rename(columns={
            "gc_id": "loading_city_gcid", "region": "origin_region",
            "latitude": "origin_lat", "longitude": "origin_lon",
        })[["loading_city_gcid", "origin_region", "origin_lat", "origin_lon"]],
        on="loading_city_gcid", how="left",
    ).merge(
        cities_small.rename(columns={
            "gc_id": "unloading_city_gcid", "region": "destination_region",
            "latitude": "destination_lat", "longitude": "destination_lon",
        })[["unloading_city_gcid", "destination_region", "destination_lat", "destination_lon"]],
        on="unloading_city_gcid", how="left",
    )

    # Время: год, sin/cos месяца, дня недели, дня года
    d = pd.to_datetime(df["loading_date"])
    df["year"] = d.dt.year
    df["month_sin"] = d.dt.month.apply(lambda m: math.sin(2 * math.pi * m / 12))
    df["month_cos"] = d.dt.month.apply(lambda m: math.cos(2 * math.pi * m / 12))
    df["dow_sin"] = d.dt.dayofweek.apply(lambda x: math.sin(2 * math.pi * x / 7))
    df["dow_cos"] = d.dt.dayofweek.apply(lambda x: math.cos(2 * math.pi * x / 7))
    df["doy_sin"] = d.dt.dayofyear.apply(lambda x: math.sin(2 * math.pi * x / 365.25))
    df["doy_cos"] = d.dt.dayofyear.apply(lambda x: math.cos(2 * math.pi * x / 365.25))

    # Целевая переменная
    df["target"] = df["price_rub"]
    return df


# Список признаков (явно, чтобы не тащить утечки)
FEATURES = [
    "distance", "total_weight", "total_volume",
    "origin_region", "destination_region",
    "origin_lat", "origin_lon", "destination_lat", "destination_lon",
    "body_group", "weight_category",
    "year", "month_sin", "month_cos", "dow_sin", "dow_cos", "doy_sin", "doy_cos",
]

CAT_FEATURES = ["origin_region", "destination_region", "body_group", "weight_category"]


def load_and_build(as_of: str, include_future: bool = False) -> pd.DataFrame:
    with get_connection() as conn:
        cities = load_cities(conn)
        prices = load_prices(conn, as_of, include_future)
    return build_features(prices, cities)