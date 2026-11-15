select
    sku,
    product_name,
    category,
    brand_type,
    cast(unit_cost as decimal(10, 2))  as unit_cost,
    cast(unit_price as decimal(10, 2)) as unit_price,
    cast(case_pack as integer)         as case_pack
from {{ source('raw', 'products') }}
