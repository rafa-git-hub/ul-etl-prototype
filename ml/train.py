import sys
import numpy as np
from catboost import CatBoostRegressor, Pool
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from features import load_and_build, FEATURES, CAT_FEATURES

AS_OF = "2026-10-26"
TRAIN_START = "2026-07-26"
TRAIN_END = "2026-10-05"   # не включительно
TEST_START = "2026-10-05"
TEST_END = "2026-10-26"
RANDOM_SEED = 42


def mape(y_true, y_pred):
    mask = y_true != 0
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def main():
    print("Загружаю признаки...")
    df = load_and_build(AS_OF)
    print(f"Всего строк: {len(df)}")

    # Time-Based Split по loading_date
    d = df["loading_date"].astype(str)
    train = df[(d >= TRAIN_START) & (d < TRAIN_END)].copy()
    test = df[(d >= TEST_START) & (d <= TEST_END)].copy()
    print(f"train: {len(train)} строк, test: {len(test)} строк")

    if len(train) == 0 or len(test) == 0:
        print("ОШИБКА: пустой train или test. Проверь окна дат.")
        sys.exit(1)

    # Заполняем пропуски в категориальных
    for c in CAT_FEATURES:
        train[c] = train[c].fillna("unknown").astype(str)
        test[c] = test[c].fillna("unknown").astype(str)

    # Обучение
    print("Обучаю CatBoost...")
    model = CatBoostRegressor(
        iterations=300,
        depth=6,
        learning_rate=0.05,
        random_seed=RANDOM_SEED,
        verbose=False,
    )
    train_pool = Pool(train[FEATURES], train["target"], cat_features=CAT_FEATURES)
    model.fit(train_pool)

    # Предсказание на test
    test_pool = Pool(test[FEATURES], cat_features=CAT_FEATURES)
    pred = model.predict(test_pool)

    # Метрики
    y_true = test["target"].values
    rmse = float(np.sqrt(mean_squared_error(y_true, pred)))
    mae = float(mean_absolute_error(y_true, pred))
    r2 = float(r2_score(y_true, pred))
    mape_val = mape(y_true, pred)

    print(f"\n=== Метрики на test ===")
    print(f"R²:   {r2:.4f}")
    print(f"MAPE: {mape_val:.2f}%")
    print(f"RMSE: {rmse:.2f} руб.")
    print(f"MAE:  {mae:.2f} руб.")


if __name__ == "__main__":
    main()