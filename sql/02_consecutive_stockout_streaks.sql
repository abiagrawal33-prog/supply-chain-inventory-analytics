-- Find store x SKU combinations stocked out 3+ weeks in a row (chronic gaps,
-- not one-off misses). Classic gaps-and-islands pattern.
with flagged as (
    select
        store_id,
        sku,
        week_start,
        is_stockout,
        row_number() over (partition by store_id, sku order by week_start)
          - row_number() over (partition by store_id, sku, is_stockout order by week_start) as island_id
    from marts.fct_inventory_weekly
),

streaks as (
    select
        store_id,
        sku,
        min(week_start)   as streak_start,
        max(week_start)   as streak_end,
        count(*)          as weeks_in_streak
    from flagged
    where is_stockout
    group by store_id, sku, island_id
)

select s.*, st.store_name, p.product_name, p.category
from streaks s
join marts.dim_store st using (store_id)
join marts.dim_product p using (sku)
where weeks_in_streak >= 3
order by weeks_in_streak desc, streak_start;
