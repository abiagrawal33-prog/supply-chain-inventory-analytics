select distinct
    week_start,
    week_start + interval 6 day                   as week_end,
    extract(isoyear from week_start)              as iso_year,
    extract(week from week_start)                 as iso_week,
    strftime(week_start, '%b %d, %Y')             as week_label,
    dense_rank() over (order by week_start)       as week_number,
    case when extract(month from week_start) in (12, 1, 2) then 'Winter'
         when extract(month from week_start) in (9, 10, 11) then 'Fall'
         else 'Other' end                         as season
from {{ ref('stg_inventory_weekly') }}
