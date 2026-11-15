-- Forecast accuracy by category x week.
--   WAPE  = sum(|forecast - demand|) / sum(demand)    (volume-weighted, robust to slow movers)
--   Bias  = sum(forecast - demand) / sum(demand)      (negative = under-forecasting)
--   Accuracy = 1 - WAPE
-- Demand is unconstrained demand (sales + estimated lost sales), so stockouts
-- don't make the forecast look better than it is.
with base as (
    select *
    from {{ ref('int_inventory_enriched') }}
    where not is_missing_forecast
),

weekly as (
    select
        week_start,
        category,
        sum(demand_units)               as demand_units,
        sum(forecast_units)             as forecast_units,
        sum(abs_forecast_error_units)   as abs_error_units,
        sum(forecast_error_units)       as error_units
    from base
    group by 1, 2
)

select
    week_start,
    category,
    demand_units,
    forecast_units,
    {{ safe_divide('abs_error_units', 'demand_units') }}                  as wape,
    1 - {{ safe_divide('abs_error_units', 'demand_units') }}              as forecast_accuracy,
    {{ safe_divide('error_units', 'demand_units') }}                      as bias,
    1 - sum(abs_error_units) over w4 / nullif(sum(demand_units) over w4, 0) as forecast_accuracy_rolling_4wk,
    sum(error_units) over w4 / nullif(sum(demand_units) over w4, 0)       as bias_rolling_4wk,
    rank() over (partition by week_start order by abs_error_units * 1.0 / nullif(demand_units, 0) desc)
                                                                           as worst_category_rank
from weekly
window w4 as (partition by category order by week_start rows between 3 preceding and current row)
