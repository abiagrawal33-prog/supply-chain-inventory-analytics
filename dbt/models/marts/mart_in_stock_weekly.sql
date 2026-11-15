-- In-stock rate by week x DC x category, with a rolling 4-week view and
-- week-over-week change for trend monitoring.
with weekly as (
    select
        week_start,
        dc_id,
        category,
        count(*)                                        as store_sku_weeks,
        sum(case when is_stockout then 1 else 0 end)    as stockout_weeks,
        sum(lost_sales_dollars)                         as lost_sales_dollars,
        sum(sales_dollars)                              as sales_dollars
    from {{ ref('int_inventory_enriched') }}
    group by 1, 2, 3
)

select
    *,
    1 - stockout_weeks * 1.0 / store_sku_weeks           as in_stock_rate,
    1 - sum(stockout_weeks) over w4 * 1.0
        / sum(store_sku_weeks) over w4                    as in_stock_rate_rolling_4wk,
    (1 - stockout_weeks * 1.0 / store_sku_weeks)
      - lag(1 - stockout_weeks * 1.0 / store_sku_weeks) over (
            partition by dc_id, category order by week_start)  as in_stock_wow_change
from weekly
window w4 as (partition by dc_id, category order by week_start rows between 3 preceding and current row)
