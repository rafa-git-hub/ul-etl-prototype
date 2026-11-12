from typing import Optional

def calc_weight_category(weight: Optional[float]) -> str:
    if weight is None:
        return "OTH"
    w = round(weight, 1)
    if w >= 30.0:
        return "G20T"
    if w >= 10.0:
        return "FTL"
    if w >= 5.0:
        return "10T"
    if w >= 2.5:
        return "5T"
    if w >= 0.5:
        return "L5T"
    return "OTH"



def calc_volume_category(volume: Optional[float]) -> str:
    if volume is None:
        return "OTH"
    if 0 < volume <= 120:
        return "FTL"
    return "OTH"


BODY_TYPE_TO_STD_ID = {
    # Тент (std_id = 56)
    56: 56, 57: 56, 58: 56, 59: 56, 60: 56, 61: 56,
    # Рефрижератор (std_id = 4)
    4: 4, 46: 4, 47: 4, 48: 4,
    # Изотерм (std_id = 2)
    2: 2,
    # Борт (std_id = 15)
    1: 15, 15: 15,
}


def body_type_to_group(body_type_id: Optional[int]) -> str:
    if body_type_id is None:
        return "unknown"
    std_id = BODY_TYPE_TO_STD_ID.get(body_type_id)
    if std_id is None:
        return "other"

    if std_id == 56:
        return "tent"
    if std_id == 4:
        return "ref"
    if std_id == 2:
        return "iso"
    if std_id == 15:
        return "bort"
    return "other"


def body_group_from_price_body_types(
        body_type_ids: list,
        fallback_body_type: Optional[int],
) -> str:
    if body_type_ids:
        for bt in body_type_ids:
            grp = body_type_to_group(bt)
            if grp not in ("other", "unknown"):
                return grp

    return body_type_to_group(fallback_body_type)