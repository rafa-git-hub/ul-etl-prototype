-- 001_core.sql
-- Слой core: очищенные данные + карантин
-- Применяется ОДИН раз: python3 etl/apply_migrations.py
-- Идемпотентно: IF NOT EXISTS — повторный запуск не ломает

-- Схема core
create schema if not exists core;

-- Таблица: core.prices_clean
-- Очищенные и обогащённые сделки (только валидные, без выбросов)
create table if not exists core.prices_clean (
    id bigserial primary key,
    source_price_id bigint not null,
    loading_date date not null,
    loading_city_gcid integer not null,
    unloading_city_gcid integer not null,
    distance double precision not null,
    total_weight double precision not null,
    total_volume double precision not null,
    body_group varchar(16) not null,
    price_original double precision not null,
    currency_code varchar(3) not null,
    price_rub double precision not null,
    weight_category varchar(4) not null,
    volume_category varchar(4) not null,
    outlier_mark boolean not null,
    etl_loaded_at timestamp not null default now(),
    unique (source_price_id)
);

-- Индексы для быстрого поиска в Mart Layer
create index if not exists idx_prices_clean_route
    on core.prices_clean (loading_city_gcid, unloading_city_gcid);
create index if not exists idx_prices_clean_loading_date
    on core.prices_clean (loading_date);
create index if not exists idx_prices_clean_body_weight
    on core.prices_clean (body_group, weight_category);

-- Таблица: core.dq_quarantine_prices
-- Строки, которые НЕ прошли валидацию (с причиной)
create table if not exists core.dq_quarantine_prices (
    id bigserial primary key,
    source_price_id bigint not null,
    reason_code varchar(40) not null,
    details text,
    etl_loaded_at timestamp not null default now(),
    unique (source_price_id, reason_code)
);
create index if not exists idx_quarantine_reason
    on core.dq_quarantine_prices (reason_code);