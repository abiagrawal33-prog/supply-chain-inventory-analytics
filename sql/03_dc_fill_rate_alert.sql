-- DC fill-rate alert: flag any DC whose fill rate has been below 90% for
-- 2+ consecutive weeks. This is the logic behind the ops dashboard alert.
with weekly as (
    select
        dc_id,
        week_start,
        sum(dc_shipped_units) * 1.0 / nullif(sum(dc_ordered_units), 0) as fill_rate
    from marts.fct_inventory_weekly
    group by 1, 2
),

flagged as (
    select
        *,
        fill_rate < 0.90                                                       as below_target,
        lag(fill_rate < 0.90) over (partition by dc_id order by week_start)    as prior_below_target
    from weekly
)

select dc_id, week_start, round(fill_rate, 3) as fill_rate
from flagged
where below_target and prior_below_target
order by dc_id, week_start;
