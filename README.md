# UL ETL — тестовое задание Data Engineer

Прототип пайплайна данных для «Умной Логистики»: очистка сделок, витрина рыночных ставок и прогноз тарифа.

## Стек

- **PostgreSQL 17** — хранилище, слои `public` → `core` → `mart`
- **Python 3.11** (`psycopg`, `pandas`) — ETL и ML
- **CatBoost** — модель прогноза
- **Docker Compose** — запуск одной командой

## Архитектура

```
public (сырые данные) → core (очищенные) → mart (витрины)
```

- **`public`** — то, что отдал заказчик: `prices`, `cities`, `body_types`, `exchange_rates`. Не трогаю.
- **`core`** — результат ETL: `prices_clean` (валидные сделки) + `dq_quarantine_prices` (отбракованные с причиной).
- **`mart`** — витрины для BI и ML: `route_card` (коридор ставок), `ml_price_predictions` (прогноз vs факт).

## Как запустить

```bash
docker compose up -d --build
```

Одна команда поднимает:

1. Postgres 17 с init-скриптами (`schema.sql`, `synthetic.sql` — 300 000 сделок).
2. Контейнер `bootstrap`: ждёт Postgres, применяет миграции (`core`, `mart`), запускает ETL, заполняет витрину, обучает модель, делает batch inference.

Проверить, что всё прошло:

```bash
docker compose logs bootstrap | tail -20
```

Ожидаемо в конце: `=== BOOTSTRAP DONE ===`.

## Что сделано

### Вопрос 1. ETL и Data Quality

- **Валидация:** `price <= 0`, `price <= 1000` для RUB, `distance <= 0`, `weight < 0`, `volume < 0`, нет города в `cities` → карантин с `reason_code`.
- **Валюты:** 840/978 конвертируются в RUB по `nearest_rate_date`. Если курса нет — карантин (`CURRENCY_RATE_MISSING`).
- **Обогащение:** `weight_category` и `volume_category` заполняются по весу/объёму. Кузов унифицируется в `body_group` (`tent` / `ref` / `iso` / `bort` / `other` / `unknown`).
- **Идемпотентность:** `UNIQUE (source_price_id)` + `INSERT ... ON CONFLICT DO UPDATE`. Повторный запуск не задваивает.
- **Backfill:** параметры `--start` / `--end`.

Запуск вручную:

```bash
python3 etl/pipeline.py --start 2023-06-01 --end 2026-10-26
```

### Вопрос 2. Витрина `mart.route_card`

Grain: месяц × город отправления × город назначения × группа кузова × весовая категория.

Метрики:

- `p25_trip`, `median_trip`, `p75_trip`, `avg_trip` (руб./рейс)
- `p25_km`, `median_km`, `p75_km` (руб./км)
- `trips_count`, `carriers_count`, `cv_rate`
- `mom_pct`, `yoy_pct`
- `reliability_level` (`HIGH` / `MEDIUM` / `LOW_DATA`)

Города дедуплицируются через `DISTINCT ON (gc_id) ... ORDER BY gc_id, id` — это устраняет дубли `gc_id`. Кузов унифицируется до одной группы на сделку, чтобы не задваивать строки в витрине.

### Вопрос 3. ML

- **Признаки:** `distance`, `total_weight`, `total_volume`, регион отправления и назначения (раздельно), координаты, группа кузова, весовая категория, `year`, sin/cos месяца, дня недели, дня года.
- **Защита от утечек:** не используются `price / distance`, `price / weight`, `price_group_stats`, `price_with_vat`. Трансформеры обучаются только на `train`.
- **Time-Based Split:** `train = [2026-07-26, 2026-10-05)`, `test = [2026-10-05, 2026-10-26]`. Случайного перемешивания нет.
- **Модель:** `CatBoostRegressor`, `random_seed=42`.

Метрики на test:

| Метрика | Значение |
|---|---|
| R² | 0.793 |
| MAPE | 19.8 % |
| RMSE | 93 924 ₽ |
| MAE | 35 382 ₽ |

Ориентир R&D-отчёта — R² ≈ 0.93, MAPE ≈ 13 %. Разница объясняется синтетикой и коротким train-окном (24 725 строк).

Batch Inference пишет прогнозы в `mart.ml_price_predictions`. Для будущих заявок (`loading_date > 2026-10-26`) `actual_price_rub`, `abs_error_rub`, `ape_pct` равны `NULL` — как требует README.

## Проверка результатов

После `docker compose up`:

```sql
-- сколько очищенных сделок
SELECT count(*) FROM core.prices_clean;

-- сколько строк в карантине и по каким причинам
SELECT reason_code, count(*) FROM core.dq_quarantine_prices GROUP BY 1 ORDER BY 2 DESC;

-- витрина: топ-5 маршрутов по числу рейсов
SELECT month, loading_city_gcid, unloading_city_gcid,
       body_group, weight_category,
       median_trip, p25_trip, p75_trip, trips_count, reliability_level
FROM mart.route_card
ORDER BY trips_count DESC
LIMIT 5;

-- прогноз vs факт
SELECT price_id, loading_date, actual_price_rub, predicted_price_rub, ape_pct
FROM mart.ml_price_predictions
WHERE actual_price_rub IS NOT NULL
LIMIT 5;

-- будущие заявки (без факта)
SELECT count(*) FROM mart.ml_price_predictions WHERE actual_price_rub IS NULL;
```

## Структура репозитория

```
.
├── docker-compose.yml
├── docker/
│   ├── Dockerfile.bootstrap
│   ├── bootstrap.sh
│   └── postgres/init/        # schema.sql, synthetic.sql
├── sql/migrations/           # 001_core, 002_mart, 003_route_card, 004, 005
├── etl/                      # connection, dq_rules, currency, categories, pipeline
├── ml/                       # features, train, predict
├── requirements.txt
└── .env.example
```

## Ограничения

- ClickHouse, Airflow, Superset — задачи со звёздочкой, не реализованы.
- Пересчёт `outlier_mark` не делается — используется входной флаг из источника.
- Сделки за последний день снимка (`2026-10-26`) могут иметь `outlier_mark = false` по умолчанию — ограничение исходных данных.

## Что можно улучшить

- Тесты на правила DQ и идемпотентность (`pytest`).
- Feature engineering: лаги, скользящие средние по маршрутам.
- Оркестрация через Airflow (DAG `@hourly`).