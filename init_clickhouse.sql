create database if not exists analytics;

create table if not exists analytics.delivery_metrics
(
    window_start DateTime,
    region String,
    event_type String,
    total_orders UInt64,
    total_amount Decimal(18, 2),
    unique_drivers UInt64,
    version DateTime
)
engine = ReplacingMergeTree(version)
partition by toYYYYMM(window_start)
order by (region, event_type, window_start);
