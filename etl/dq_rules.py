from dataclasses import dataclass
from typing import Optional

REASON_PRICE_LE_ZERO = "PRICE_LE_ZERO"
REASON_PRICE_LE_1000_RUB = "PRICE_LE_1000_RUB"
REASON_DISTANCE_LE_ZERO = "DISTANCE_LE_ZERO"
REASON_WEIGHT_NEGATIVE = "WEIGHT_NEGATIVE"
REASON_VOLUME_NEGATIVE = "VOLUME_NEGATIVE"
REASON_CITY_NOT_FOUND = "CITY_NOT_FOUND"
REASON_CURRENCY_RATE_MISSING = "CURRENCY_RATE_MISSING"


@dataclass
class DQResult:
    """Вердикт по одной строке."""
    is_valid: bool
    reason_code: Optional[str] = None
    details: Optional[str] = None


def validate_price_row(row: dict, city_gcids: set) -> DQResult:
    """
    Проверяет одну строку из public.prices.

    row — словарь с полями:
      price, currency_code, distance, total_weight, total_volume,
      loading_city_gcid, unloading_city_gcid, nearest_rate_date

    city_gcids — множество существующих gc_id из cities.

    Возвращает DQResult:
      - is_valid=True → строка ок
      - is_valid=False → карантин, reason_code + details
    """
    # 1. Цена должна быть > 0
    price = row["price"]
    if price is None or price <= 0:
        return DQResult(
            is_valid=False,
            reason_code=REASON_PRICE_LE_ZERO,
            details=f"price={price}",
        )

    # 2. Для RUB: цена должна быть > 1000 (source-validation)
    currency = row["currency_code"]
    if currency == "643" and price <= 1000:
        return DQResult(
            is_valid=False,
            reason_code=REASON_PRICE_LE_1000_RUB,
            details=f"price={price} (RUB)",
        )

    # 3. Дистанция должна быть > 0
    distance = row["distance"]
    if distance is None or distance <= 0:
        return DQResult(
            is_valid=False,
            reason_code=REASON_DISTANCE_LE_ZERO,
            details=f"distance={distance}",
        )

    # 4. Вес не может быть отрицательным
    weight = row["total_weight"]
    if weight is None or weight < 0:
        return DQResult(
            is_valid=False,
            reason_code=REASON_WEIGHT_NEGATIVE,
            details=f"total_weight={weight}",
        )

    # 5. Объём не может быть отрицательным
    volume = row["total_volume"]
    if volume is None or volume < 0:
        return DQResult(
            is_valid=False,
            reason_code=REASON_VOLUME_NEGATIVE,
            details=f"total_volume={volume}",
        )

    # 6. Оба города должны быть в справочнике cities
    lc = row["loading_city_gcid"]
    uc = row["unloading_city_gcid"]
    if lc not in city_gcids or uc not in city_gcids:
        missing = []
        if lc not in city_gcids:
            missing.append(f"loading={lc}")
        if uc not in city_gcids:
            missing.append(f"unloading={uc}")
        return DQResult(
            is_valid=False,
            reason_code=REASON_CITY_NOT_FOUND,
            details="missing: " + ", ".join(missing),
        )

    # 7. Для иностранной валюты должен быть nearest_rate_date
    #    (сам курс проверит etl/currency.py)
    if currency in ("840", "978") and row["nearest_rate_date"] is None:
        return DQResult(
            is_valid=False,
            reason_code=REASON_CURRENCY_RATE_MISSING,
            details=f"currency={currency}, nearest_rate_date=NULL",
        )

    # Все проверки пройдены
    return DQResult(is_valid=True)