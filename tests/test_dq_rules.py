# tests/test_dq_rules.py
# Проверяет правила DQ из etl/dq_rules.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))

from dq_rules import validate_price_row, REASON_PRICE_LE_ZERO, REASON_PRICE_LE_1000_RUB


def make_row(**kwargs):
    """Базовый валидный ряд, поверх которого можно менять поля."""
    base = {
        "price": 50000.0,
        "currency_code": "643",
        "distance": 1000.0,
        "total_weight": 20.0,
        "total_volume": 60.0,
        "loading_city_gcid": 1001,
        "unloading_city_gcid": 1003,
        "nearest_rate_date": None,
    }
    base.update(kwargs)
    return base


def test_price_zero_goes_to_quarantine():
    row = make_row(price=0.0)
    result = validate_price_row(row, {1001, 1003})
    assert result.is_valid is False
    assert result.reason_code == REASON_PRICE_LE_ZERO


def test_rub_price_le_1000_goes_to_quarantine():
    row = make_row(price=500.0, currency_code="643")
    result = validate_price_row(row, {1001, 1003})
    assert result.is_valid is False
    assert result.reason_code == REASON_PRICE_LE_1000_RUB


def test_valid_row_passes():
    row = make_row(price=50000.0)
    result = validate_price_row(row, {1001, 1003})
    assert result.is_valid is True
    assert result.reason_code is None