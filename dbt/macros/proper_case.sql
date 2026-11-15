{# Title-case each word: 'FORT WORTH #1004' -> 'Fort Worth #1004'. Snowflake/Databricks have initcap(); DuckDB doesn't. #}
{% macro proper_case(col) -%}
    {%- if target.type == 'duckdb' -%}
    array_to_string(list_transform(string_split(lower({{ col }}), ' '), lambda w: upper(w[1]) || w[2:]), ' ')
    {%- else -%}
    initcap({{ col }})
    {%- endif -%}
{%- endmacro %}
