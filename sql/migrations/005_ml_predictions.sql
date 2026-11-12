CREATE TABLE IF NOT EXISTS mart.ml_price_predictions (
    id                  bigserial PRIMARY KEY,
    price_id            bigint NOT NULL,
    loading_date        date NOT NULL,
    loading_city_gcid   integer NOT NULL,
    unloading_city_gcid integer NOT NULL,
    body_group          varchar(16) NOT NULL,
    actual_price_rub    double precision,
    predicted_price_rub double precision NOT NULL,
    abs_error_rub       double precision,
    ape_pct             double precision,
    model_name          varchar(50) NOT NULL,
    scored_at           timestamp NOT NULL DEFAULT now(),
    UNIQUE (price_id, model_name)
);

CREATE INDEX IF NOT EXISTS idx_ml_pred_loading_date
    ON mart.ml_price_predictions (loading_date);