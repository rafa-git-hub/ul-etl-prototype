from typing import Optional

FOREIGN_CURRENCIES = {"840", "978"}


def convert_to_rub(
        price: float,
        currency_code: str,
        rate: Optional[float],
) -> Optional[float]:

    if currency_code == "643":
        return price

    # Иностранная валюта: нужен курс
    if currency_code in FOREIGN_CURRENCIES:
        if rate is None or rate <= 0:
            return None  # карантин — вызывающий код разберётся
        return price * rate

    # Неизвестная валюта (например, '000' или NULL) — тоже карантин
    return None


def load_exchange_rates(conn) -> dict:
    rates = {}
    with conn.cursor() as cur:
        cur.execute("SELECT num_code, setting_date, value FROM exchange_rates")
        for num_code, setting_date, value in cur.fetchall():
            rates[(num_code, setting_date)] = float(value)
    return rates


def get_rate(
        rates: dict,
        currency_code: str,
        nearest_rate_date,
) -> Optional[float]:

    if nearest_rate_date is None:
        return None
    return rates.get((currency_code, nearest_rate_date))