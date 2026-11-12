-- tests/test_idempotency.sql
-- Проверяет: нет дублей в core.prices_clean (UNIQUE работает)
-- Запуск: docker exec -i ul-postgres psql -U ul -d deals_bigdata -f tests/test_idempotency.sql

-- 1. Не должно быть дублей по source_price_id
DO $$
DECLARE
    dup_count integer;
BEGIN
    SELECT count(*) INTO dup_count
    FROM (
        SELECT source_price_id FROM core.prices_clean
        GROUP BY source_price_id HAVING count(*) > 1
    ) t;
    IF dup_count > 0 THEN
        RAISE EXCEPTION 'FAIL: % дублей по source_price_id', dup_count;
    END IF;
    RAISE NOTICE 'OK: дублей нет';
END $$;

-- 2. Не должно быть NULL в ключевых полях
DO $$
DECLARE
    null_count integer;
BEGIN
    SELECT count(*) INTO null_count
    FROM core.prices_clean
    WHERE price_rub IS NULL OR body_group IS NULL OR weight_category IS NULL;
    IF null_count > 0 THEN
        RAISE EXCEPTION 'FAIL: % строк с NULL в ключевых полях', null_count;
    END IF;
    RAISE NOTICE 'OK: NULL в ключевых полях отсутствуют';
END $$;