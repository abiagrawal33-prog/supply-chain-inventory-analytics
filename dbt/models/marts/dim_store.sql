select
    s.store_id,
    s.store_name,
    s.city,
    s.region,
    s.store_format,
    s.dc_id,
    dc.dc_name,
    s.open_date
from {{ ref('stg_stores') }} s
left join {{ ref('stg_distribution_centers') }} dc using (dc_id)
