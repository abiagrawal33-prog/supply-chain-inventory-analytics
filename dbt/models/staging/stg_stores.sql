-- Store master. Source names arrive in mixed case, so normalize them.
select
    store_id,
    -- e.g. 'DALLAS #1001' -> 'Dallas #1001'
    {{ proper_case('store_name') }} as store_name,
    city,
    region,
    store_format,
    dc_id,
    cast(open_date as date) as open_date
from {{ source('raw', 'stores') }}
