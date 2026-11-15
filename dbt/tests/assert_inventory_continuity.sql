-- This week's begin on hand must equal last week's end on hand.
select *
from (
    select
        store_id, sku, week_start, begin_on_hand,
        lag(end_on_hand) over (partition by store_id, sku order by week_start) as prior_end
    from {{ ref('fct_inventory_weekly') }}
)
where prior_end is not null and begin_on_hand <> prior_end
