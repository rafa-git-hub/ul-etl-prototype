# tests/test_categories.py
# Проверяет обогащение категорий из etl/categories.py

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))

from categories import (
    calc_weight_category,
    calc_volume_category,
    body_type_to_group,
    body_group_from_price_body_types,
)


def test_weight_category_boundaries():
    assert calc_weight_category(31.0) == "G20T"
    assert calc_weight_category(30.0) == "G20T"
    assert calc_weight_category(29.9) == "FTL"
    assert calc_weight_category(10.0) == "FTL"
    assert calc_weight_category(5.0) == "10T"
    assert calc_weight_category(2.5) == "5T"
    assert calc_weight_category(0.5) == "L5T"
    assert calc_weight_category(0.4) == "OTH"
    assert calc_weight_category(None) == "OTH"


def test_volume_category():
    assert calc_volume_category(60.0) == "FTL"
    assert calc_volume_category(120.0) == "FTL"
    assert calc_volume_category(121.0) == "OTH"
    assert calc_volume_category(0.0) == "OTH"
    assert calc_volume_category(None) == "OTH"


def test_body_type_to_group():
    assert body_type_to_group(56) == "tent"
    assert body_type_to_group(57) == "tent"
    assert body_type_to_group(4) == "ref"
    assert body_type_to_group(46) == "ref"
    assert body_type_to_group(2) == "iso"
    assert body_type_to_group(1) == "bort"
    assert body_type_to_group(None) == "unknown"
    assert body_type_to_group(999) == "other"


def test_body_group_from_price_body_types():
    # Первый осмысленный тип из списка
    assert body_group_from_price_body_types([56, 15], None) == "tent"
    # Мусорные типы → fallback на body_type
    assert body_group_from_price_body_types([999], 56) == "tent"
    # Пустой список → fallback
    assert body_group_from_price_body_types([], 4) == "ref"