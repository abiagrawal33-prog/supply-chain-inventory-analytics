-- One row per store x SKU x week with the inventory position, the DC shipment
-- that fed it, product/store attributes and the flags every mart relies on.
with inv as (
    select * from {{ ref('stg_inventory_weekly') }}
),

ship as (
    select * from {{ ref('stg_dc_shipments') }}
),

stores as (
    select * from {{ ref('stg_stores') }}
),

products as (
    select * from {{ ref('stg_products') }}
)

select
    inv.week_start,
    inv.store_id,
    stores.region,
    stores.store_format,
    stores.dc_id,
    inv.sku,
    products.category,
    products.brand_type,
    products.unit_price,

    inv.begin_on_hand,
    inv.receipts,
    inv.begin_on_hand + inv.receipts                         as available_units,
    inv.demand_units,
    inv.sales_units,
    inv.lost_sales_units,
    inv.end_on_hand,
    inv.forecast_units,
    inv.is_missing_forecast,
    inv.order_units,
    inv.safety_stock_weeks,

    ship.ordered_units                                       as dc_ordered_units,
    ship.shipped_units                                       as dc_shipped_units,
    ship.days_late                                           as dc_days_late,
    {{ safe_divide('ship.shipped_units', 'ship.ordered_units') }} as dc_fill_rate,

    inv.lost_sales_units > 0                                 as is_stockout,
    inv.lost_sales_units * products.unit_price               as lost_sales_dollars,
    inv.sales_units * products.unit_price                    as sales_dollars,
    inv.forecast_units - inv.demand_units                    as forecast_error_units,
    abs(inv.forecast_units - inv.demand_units)               as abs_forecast_error_units
from inv
inner join stores   on inv.store_id = stores.store_id
inner join products on inv.sku = products.sku
left join ship
    on  inv.week_start = ship.week_start
    and inv.store_id   = ship.store_id
    and inv.sku        = ship.sku
