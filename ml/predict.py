import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "etl"))

import numpy as np
from catboost import CatBoostRegressor, Pool

from connection import get_connection
from features import load_and_build, FEATURES, CAT_FEATURES

AS_OF = "2026-10-26"
TRAIN_START = "2026-07-26"
TRAIN_END = "2026-10-05"
TEST_START = "2026-10-05"
MODEL_NAME = "catboost_v1"
RANDOM_SEED = 42


def main():
    print("Загружаю признаки...")
    df = load_and_build(AS_OF, include_future=True)
    print(f"Всего строк: {len(df)}")

    # Разделяем
    d = df["loading_date"].astype(str)
    train = df[(d >= TRAIN_START) & (d < TRAIN_END)].copy()
    score = df[(d >= TEST_START)].copy()  # test + будущие
    print(f"train: {len(train)}, к скорингу: {len(score)}")

    # Обучение
    for c in CAT_FEATURES:
        train[c] = train[c].fillna("unknown").astype(str)
        score[c] = score[c].fillna("unknown").astype(str)

    print("Обучаю модель...")
    model = CatBoostRegressor(
        iterations=300, depth=6, learning_rate=0.05,
        random_seed=RANDOM_SEED, verbose=False,
    )
    train_pool = Pool(train[FEATURES], train["target"], cat_features=CAT_FEATURES)
    model.fit(train_pool)

    # Скоринг
    print("Скоринг...")
    score_pool = Pool(score[FEATURES], cat_features=CAT_FEATURES)
    score["predicted_price_rub"] = model.predict(score_pool)

    # Готовим строки для вставки
    rows = []
    for _, r in score.iterrows():
        actual = r["target"] if r["loading_date"] <= pd_to_date(AS_OF) else None
        pred = r["predicted_price_rub"]
        if actual is not None and actual > 0:
            abs_err = abs(actual - pred)
            ape = abs_err / actual * 100
        else:
            abs_err = None
            ape = None
        rows.append({
            "price_id": int(r["source_price_id"]),
            "loading_date": r["loading_date"],
            "loading_city_gcid": int(r["loading_city_gcid"]),
            "unloading_city_gcid": int(r["unloading_city_gcid"]),
            "body_group": r["body_group"],
            "actual_price_rub": float(actual) if actual is not None else None,
            "predicted_price_rub": float(pred),
            "abs_error_rub": float(abs_err) if abs_err is not None else None,
            "ape_pct": float(ape) if ape is not None else None,
            "model_name": MODEL_NAME,
        })

    # Запись в БД (батчами, идемпотентно)
    print(f"Пишу {len(rows)} строк в mart.ml_price_predictions...")
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.executemany("""
                INSERT INTO mart.ml_price_predictions (
                    price_id, loading_date, loading_city_gcid, unloading_city_gcid,
                    body_group, actual_price_rub, predicted_price_rub,
                    abs_error_rub, ape_pct, model_name
                ) VALUES (
                    %(price_id)s, %(loading_date)s, %(loading_city_gcid)s, %(unloading_city_gcid)s,
                    %(body_group)s, %(actual_price_rub)s, %(predicted_price_rub)s,
                    %(abs_error_rub)s, %(ape_pct)s, %(model_name)s
                )
                ON CONFLICT (price_id, model_name) DO UPDATE SET
                    predicted_price_rub = EXCLUDED.predicted_price_rub,
                    actual_price_rub = EXCLUDED.actual_price_rub,
                    abs_error_rub = EXCLUDED.abs_error_rub,
                    ape_pct = EXCLUDED.ape_pct,
                    scored_at = now()
            """, rows)
        conn.commit()
    print("Готово.")


def pd_to_date(s: str):
    from datetime import date
    return date.fromisoformat(s)


if __name__ == "__main__":
    main()