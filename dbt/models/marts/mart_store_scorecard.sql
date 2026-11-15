-- One row per store: the scorecard planners review in the weekly ops meeting.
with by_store as (
    select
        store_id,
        count(*)                                                as store_sku_weeks,
        1 - avg(case when is_stockout then 1.0 else 0.0 end)    as in_stock_rate,
        sum(lost_sales_dollars)                                 as lost_sales_dollars,
        sum(sales_dollars)                                      as sales_dollars,
        avg(safety_stock_weeks)                                 as avg_safety_stock_weeks
    from {{ ref('int_inventory_enriched') }}
    group by 1
)

select
    s.store_id,
    d.store_name,
    d.region,
    d.store_format,
    d.dc_id,
    s.in_stock_rate,
    s.lost_sales_dollars,
    s.sales_dollars,
    s.lost_sales_dollars / nullif(s.sales_dollars + s.lost_sales_dollars, 0) as lost_sales_pct,
    s.avg_safety_stock_weeks,
    rank()  over (order by s.in_stock_rate desc)                           as in_stock_rank,
    ntile(4) over (order by s.in_stock_rate desc)                          as performance_quartile,
    s.in_stock_rate - avg(s.in_stock_rate) over (partition by d.region)    as vs_region_avg
from by_store s
join {{ ref('dim_store') }} d using (store_id)
