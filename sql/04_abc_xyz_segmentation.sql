-- ABC (value) x XYZ (demand variability) segmentation of SKUs. Used to set
-- different service-level targets and review cadences by segment.
with sku_stats as (
    select
        sku,
        sum(sales_dollars)                                    as revenue,
        stddev_samp(weekly_demand) / nullif(avg(weekly_demand), 0) as cv
    from (
        select sku, week_start, sum(demand_units) as weekly_demand, sum(sales_dollars) as sales_dollars
        from marts.fct_inventory_weekly
        group by 1, 2
    )
    group by 1
),

ranked as (
    select
        *,
        sum(revenue) over (order by revenue desc rows between unbounded preceding and current row)
          / sum(revenue) over ()                              as cumulative_share
    from sku_stats
)

select
    case when cumulative_share <= 0.80 then 'A'
         when cumulative_share <= 0.95 then 'B'
         else 'C' end                                         as abc_class,
    case when cv < 0.15 then 'X'
         when cv < 0.30 then 'Y'
         else 'Z' end                                         as xyz_class,
    count(*)                                                  as skus,
    round(sum(revenue), 0)                                    as revenue
from ranked
group by all
order by abc_class, xyz_class;
