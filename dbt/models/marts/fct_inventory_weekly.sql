-- Grain: store x SKU x week. The central fact table for Power BI / Tableau.
select
    week_start,
    store_id,
    sku,
    dc_id,
    begin_on_hand,
    receipts,
    available_units,
    demand_units,
    sales_units,
    lost_sales_units,
    end_on_hand,
    forecast_units,
    is_missing_forecast,
    order_units,
    dc_ordered_units,
    dc_shipped_units,
    dc_fill_rate,
    dc_days_late,
    is_stockout,
    sales_dollars,
    lost_sales_dollars,
    -- weeks of supply on hand at end of week, based on trailing 4-week average sales
    {{ safe_divide(
        'end_on_hand',
        'avg(sales_units) over (partition by store_id, sku order by week_start rows between 3 preceding and current row)'
    ) }} as weeks_of_supply
from {{ ref('int_inventory_enriched') }}
