-- A store cannot sell more units than it had available in the week.
select *
from {{ ref('fct_inventory_weekly') }}
where sales_units > available_units
