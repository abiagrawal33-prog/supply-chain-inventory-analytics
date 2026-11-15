-- Inventory must roll forward: begin + receipts - sales = end.
select *
from {{ ref('fct_inventory_weekly') }}
where begin_on_hand + receipts - sales_units <> end_on_hand
