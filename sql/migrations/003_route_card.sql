-- 003_route_card.sql
-- Заполнение mart.route_card из core.prices_clean
-- Идемпотентно: DELETE + INSERT в одной транзакции
-- Параметр: :as_of (дата снимка)

BEGIN;

DELETE FROM mart.route_card WHERE as_of = :'as_of'::date;

INSERT INTO mart.route_card (
    month, loading_city_gcid, unloading_city_gcid, body_group, weight_category,
    p25_trip, median_trip, p75_trip, avg_trip,
    p25_km, median_km, p75_km,
    trips_count, carriers_count, cv_rate,
    mom_pct, yoy_pct, reliability_level, as_of
)
WITH base AS (
    SELECT
        date_trunc('month', pc.loading_date)::date AS month,
        pc.loading_city_gcid,
        pc.unloading_city_gcid,
        pc.body_group,
        pc.weight_category,
        pc.price_rub,
        pc.price_rub / NULLIF(pc.distance, 0) AS price_km,
        pc.organization_id,
        pc.price_type
    FROM core.prices_clean pc
    WHERE pc.outlier_mark = false
      AND pc.loading_date <= :'as_of'::date
),
agg AS (
    SELECT
        month, loading_city_gcid, unloading_city_gcid, body_group, weight_category,
        percentile_cont(0.25) WITHIN GROUP (ORDER BY price_rub) AS p25_trip,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY price_rub) AS median_trip,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY price_rub) AS p75_trip,
        avg(price_rub) AS avg_trip,
        percentile_cont(0.25) WITHIN GROUP (ORDER BY price_km) AS p25_km,
        percentile_cont(0.50) WITHIN GROUP (ORDER BY price_km) AS median_km,
        percentile_cont(0.75) WITHIN GROUP (ORDER BY price_km) AS p75_km,
        count(*) AS trips_count,
        count(DISTINCT organization_id) FILTER (WHERE price_type IN (3, 9)) AS carriers_count,
        CASE WHEN count(*) >= 2 AND avg(price_rub) > 0
             THEN stddev_samp(price_rub) / avg(price_rub)
             ELSE NULL END AS cv_rate
    FROM base
    GROUP BY 1, 2, 3, 4, 5
),
with_lag AS (
    SELECT
        a.*,
        LAG(a.median_trip) OVER (
            PARTITION BY a.loading_city_gcid, a.unloading_city_gcid, a.body_group, a.weight_category
            ORDER BY a.month
        ) AS prev_month_median,
        LAG(a.median_trip, 12) OVER (
            PARTITION BY a.loading_city_gcid, a.unloading_city_gcid, a.body_group, a.weight_category
            ORDER BY a.month
        ) AS prev_year_median
    FROM agg a
)
SELECT
    w.month, w.loading_city_gcid, w.unloading_city_gcid, w.body_group, w.weight_category,
    w.p25_trip, w.median_trip, w.p75_trip, w.avg_trip,
    w.p25_km, w.median_km, w.p75_km,
    w.trips_count, w.carriers_count, w.cv_rate,
    CASE WHEN w.prev_month_median > 0
         THEN (w.median_trip - w.prev_month_median) / w.prev_month_median * 100
         ELSE NULL END AS mom_pct,
    CASE WHEN w.prev_year_median > 0
         THEN (w.median_trip - w.prev_year_median) / w.prev_year_median * 100
         ELSE NULL END AS yoy_pct,
    CASE
        WHEN w.trips_count >= 30 AND w.carriers_count >= 5
             AND (:'as_of'::date - w.month) <= 30
        THEN 'HIGH'
        WHEN w.trips_count >= 10
        THEN 'MEDIUM'
        ELSE 'LOW_DATA'
    END AS reliability_level,
    :'as_of'::date
FROM with_lag w;

COMMIT;