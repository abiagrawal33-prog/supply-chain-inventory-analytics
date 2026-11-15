-- Store inventory positions. ~0.2% of rows have no forecast (planning-tool gaps);
-- keep them, flag them, and exclude them from accuracy metrics downstream.
select
    cast(week_start as date)              as week_start,
    store_id,
    sku,
    cast(begin_on_hand as integer)        as begin_on_hand,
    cast(receipts as integer)             as receipts,
    cast(demand_units as integer)         as demand_units,
    cast(sales_units as integer)          as sales_units,
    cast(lost_sales_units as integer)     as lost_sales_units,
    cast(end_on_hand as integer)          as end_on_hand,
    cast(forecast_units as double)        as forecast_units,
    cast(order_units as integer)          as order_units,
    cast(safety_stock_weeks as double)    as safety_stock_weeks,
    forecast_units is null                as is_missing_forecast
from {{ source('raw', 'inventory_weekly') }}
