select
    cast(week_start as date)     as week_start,
    dc_id,
    store_id,
    sku,
    cast(ordered_units as integer) as ordered_units,
    cast(shipped_units as integer) as shipped_units,
    cast(days_late as integer)     as days_late
from {{ source('raw', 'dc_shipments') }}
