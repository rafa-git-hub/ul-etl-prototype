-- 004_add_org_price_type.sql
-- Добавляем organization_id и price_type в core.prices_clean
-- Нужно для carriers_count в mart.route_card

ALTER TABLE core.prices_clean
    ADD COLUMN IF NOT EXISTS organization_id integer,
    ADD COLUMN IF NOT EXISTS price_type      smallint;