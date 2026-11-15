select
    sku,
    product_name,
    category,
    brand_type,
    unit_cost,
    unit_price,
    unit_price - unit_cost                           as unit_margin,
    {{ safe_divide('unit_price - unit_cost', 'unit_price') }} as margin_pct,
    case_pack
from {{ ref('stg_products') }}
