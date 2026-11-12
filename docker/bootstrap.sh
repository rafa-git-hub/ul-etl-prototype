#!/bin/bash
set -e

echo "=== BOOTSTRAP START ==="

# 1. Ждём Postgres
echo "Жду Postgres..."
until pg_isready -h postgres -U ul -d deals_bigdata; do
  sleep 2
done
echo "Postgres готов."

# 2. Применяем миграции (схемы core и mart)
echo "Применяю миграции..."
for f in sql/migrations/001_core.sql sql/migrations/002_mart.sql sql/migrations/004_add_org_price_type.sql sql/migrations/005_ml_predictions.sql; do
  echo "  → $f"
  PGPASSWORD=ul_secret psql -h postgres -U ul -d deals_bigdata -f "$f"
done

# 3. ETL: вся история + будущие
echo "Запускаю ETL (история)..."
PYTHONPATH=/app python3 etl/pipeline.py --start 2023-06-01 --end 2026-10-26

echo "Запускаю ETL (будущие)..."
PYTHONPATH=/app python3 etl/pipeline.py --start 2026-10-27 --end 2027-12-31

# 4. Витрина mart.route_card
echo "Заполняю mart.route_card..."
PGPASSWORD=ul_secret psql -h postgres -U ul -d deals_bigdata -v as_of="2026-10-26" -f sql/migrations/003_route_card.sql

# 5. ML: обучение + batch inference
echo "Запускаю ML (train + predict)..."
PYTHONPATH=/app python3 ml/predict.py

echo "=== BOOTSTRAP DONE ==="