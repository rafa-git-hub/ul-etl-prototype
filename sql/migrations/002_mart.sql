-- 002_mart.sql
-- Слой mart: витрины для BI и ML
-- Идемпотентно: IF NOT EXISTS

CREATE SCHEMA IF NOT EXISTS mart;


CREATE TABLE IF NOT EXISTS mart.route_card (
    -- Grain
    month               date        NOT NULL,
    loading_city_gcid   integer     NOT NULL,
    unloading_city_gcid integer     NOT NULL,
    body_group          varchar(16) NOT NULL,
    weight_category     varchar(4)  NOT NULL,

    -- Рыночный коридор за рейс (руб./рейс)
    p25_trip            double precision,
    median_trip         double precision,
    p75_trip            double precision,
    avg_trip            double precision,

    -- Рыночный коридор за км (руб./км)
    p25_km              double precision,
    median_km           double precision,
    p75_km              double precision,

    -- Доказательная база
    trips_count         bigint,
    carriers_count      bigint,
    cv_rate             double precision,

    -- Динамика
    mom_pct             double precision,
    yoy_pct             double precision,

    -- Надёжность
    reliability_level   varchar(10) NOT NULL,

    -- Служебное
    as_of               date NOT NULL,
    etl_loaded_at       timestamp NOT NULL DEFAULT now(),

    PRIMARY KEY (month, loading_city_gcid, unloading_city_gcid, body_group, weight_category)
);

CREATE INDEX IF NOT EXISTS idx_route_card_route
    ON mart.route_card (loading_city_gcid, unloading_city_gcid);

CREATE INDEX IF NOT EXISTS idx_route_card_month
    ON mart.route_card (month DESC);