select dc_id, dc_name, dc_state
from {{ source('raw', 'distribution_centers') }}
