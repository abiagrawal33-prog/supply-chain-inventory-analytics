-- Classify every stockout into one primary root cause, in priority order:
--   1. DC short-ship / late delivery  (supply side failed: the DC shortfall covers the lost units)
--   2. Forecast under-call            (planning failed: this week AND the trailing 4 weeks under-forecast)
--   3. Safety stock too low           (parameter failed)
--   4. Demand variability             (none of the above: normal noise)
with enriched as (
    select
        *,
        -- trailing 4-week forecast vs demand for this store x SKU: separates a
        -- persistent under-forecast from a one-week demand spike
        sum(forecast_units) over w4 / nullif(sum(demand_units) over w4, 0) as forecast_to_demand_4wk
    from {{ ref('int_inventory_enriched') }}
    window w4 as (partition by store_id, sku order by week_start rows between 3 preceding and current row)
),

stockouts as (
    select * from enriched where is_stockout
)

select
    week_start,
    store_id,
    sku,
    dc_id,
    region,
    category,
    demand_units,
    forecast_units,
    available_units,
    lost_sales_units,
    lost_sales_dollars,
    dc_fill_rate,
    dc_days_late,
    safety_stock_weeks,
    forecast_to_demand_4wk,
    case
        -- the DC shortfall alone was big enough to cause the lost sales
        when dc_fill_rate < {{ var('stockout_fill_rate_threshold') }}
             and dc_ordered_units - dc_shipped_units >= lost_sales_units
            then 'DC short-ship / late delivery'
        when forecast_units < demand_units * {{ var('forecast_undercall_ratio') }}
             and forecast_to_demand_4wk < {{ var('persistent_bias_ratio') }}
            then 'Forecast under-call'
        when safety_stock_weeks < {{ var('low_safety_stock_weeks') }}
            then 'Safety stock too low'
        else 'Demand variability'
    end as root_cause
from stockouts
