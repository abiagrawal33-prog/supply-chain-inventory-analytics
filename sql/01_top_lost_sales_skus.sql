-- Top 3 SKUs by lost sales in each category, last 8 weeks.
-- Shows: CTEs, window ranking with QUALIFY, date filtering.
with recent as (
    select *
    from marts.fct_inventory_weekly
    where week_start >= (select max(week_start) from marts.fct_inventory_weekly) - interval 7 week
),

by_sku as (
    select
        p.category,
        r.sku,
        p.product_name,
        sum(r.lost_sales_dollars)                                 as lost_sales_dollars,
        sum(case when r.is_stockout then 1 else 0 end)            as stockout_weeks,
        count(distinct case when r.is_stockout then r.store_id end) as stores_affected
    from recent r
    join marts.dim_product p using (sku)
    group by all
)

select
    *,
    rank() over (partition by category order by lost_sales_dollars desc) as rank_in_category
from by_sku
qualify rank_in_category <= 3
order by category, rank_in_category;
