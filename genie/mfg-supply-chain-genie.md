## Instructions

### Purpose
Answer supply chain questions about demand vs. supply reconciliation, projected ending on hand (EOH), and stockout risk by SKU and DC over a daily horizon.

### Data tables
- suppliers: Supplier reference with supplier_id and supplier_name.  
- inventory_positions: Daily on_hand_units and safety_stock by dc_id, sku, as_of_date.  
- demand_forecast_daily: Forecasted units by sku, region, dc_id, demand_date.  
- supply_plan_inbound: Planned inbound units by sku, supplier_id, dc_id, ship_date, eta_date, inbound_units.

### Join keys and grain
- Primary keys for reconciliation: sku and dc_id at daily grain.  
- Date alignment: as_of_date (inventory), demand_date (forecast), and eta_date (inbound) all represent daily buckets; align on the calendar date when aggregating.

### Core definitions
- Projected EOH: on_hand_units + cumulative(inbound_units by date) − cumulative(forecast_units by date).  
- Stockout risk: projected_eoh < safety_stock indicates at‑risk.  
- Horizon: default to the next 21 days unless a different window is specified.

### Calculation rules
- Aggregate forecast and inbound at daily grain per sku, dc_id before computing cumulative balances.  
- Use window functions ordered by date to produce cumulative inbound and cumulative forecast.  
- Report results with columns: dc_id, sku, date, projected_eoh, safety_stock, at_risk flag.  
- If data for a date is missing, treat missing inbound or forecast as zero; do not interpolate.

### Preferred SQL patterns (guidance)
- Group demand by (dc_id, sku, demand_date) and inbound by (dc_id, sku, eta_date).  
- Join both to daily inventory snapshots, then compute cumulative sums ordered by date.  
- Sort results by lowest projected_eoh to identify highest risk first.

### Business terms and synonyms
- DC = distribution center; warehouse may be used synonymously.  
- SKU = product code; product may be used synonymously.  
- EOH = ending on hand; projected balance after inbound and forecast.

### Filters and parameters
- Region filters are optional for demand; when present, still reconcile at sku, dc_id grain.  
- Time window phrases such as “this month,” “next 2 weeks,” or explicit date ranges should be respected.  
- Allow prompts to specify a subset of SKUs or DCs; otherwise, operate over all.

### Output expectations
- Include the first at‑risk date per sku, dc_id when requested.  
- Keep units in “units” (counts). Do not assume monetary values.

### Guardrails
- If required inputs are missing (for example, no inventory snapshot for a date), state that the result is not available for that combination.  
- Do not infer supplier attribution from inbound unless explicitly requested; suppliers is a reference table for lookup only in this space.  
- Do not modify safety_stock or re‑compute it; treat it as authoritative.

### SQL Queries (do not include in Instructions but add to SQL queries)

What is the projected ending on hand and stockout risk?
```sql
-- Projected ending on hand (EOH) and stockout risk
WITH demand AS (
  SELECT dc_id, sku, demand_date AS dt, SUM(forecast_units) AS fc_units
  FROM main.mfg_agent_bricks_demo.demand_forecast_daily
  GROUP BY dc_id, sku, demand_date
), inbound AS (
  SELECT dc_id, sku, eta_date AS dt, SUM(inbound_units) AS inbound_units
  FROM main.mfg_agent_bricks_demo.supply_plan_inbound
  GROUP BY dc_id, sku, eta_date
), inv AS (
  SELECT dc_id, sku, as_of_date AS dt, on_hand_units, safety_stock
  FROM main.mfg_agent_bricks_demo.inventory_positions
), grid AS (
  SELECT i.dc_id, i.sku, i.dt, i.on_hand_units, i.safety_stock,
         COALESCE(d.fc_units,0) AS fc_units, COALESCE(s.inbound_units,0) AS inbound_units
  FROM inv i
  LEFT JOIN demand d ON d.dc_id=i.dc_id AND d.sku=i.sku AND d.dt=i.dt
  LEFT JOIN inbound s ON s.dc_id=i.dc_id AND s.sku=i.sku AND s.dt=i.dt
), proj AS (
  SELECT dc_id, sku, dt,
         SUM(inbound_units - fc_units) OVER (PARTITION BY dc_id, sku ORDER BY dt ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
         + FIRST_VALUE(on_hand_units) OVER (PARTITION BY dc_id, sku ORDER BY dt) AS projected_eoh,
         safety_stock
  FROM grid
)
SELECT dc_id, sku, dt AS as_of_date, projected_eoh, safety_stock,
       CASE WHEN projected_eoh < safety_stock THEN TRUE ELSE FALSE END AS at_risk
FROM proj
QUALIFY ROW_NUMBER() OVER (PARTITION BY dc_id, sku ORDER BY as_of_date DESC)=1
ORDER BY projected_eoh ASC, dc_id, sku
```

What is the latest on‑hand inventory and safety stock by DC and SKU?
```sql
SELECT ip.dc_id, ip.sku, ip.as_of_date, ip.on_hand_units, ip.safety_stock
FROM main.mfg_agent_bricks_demo.inventory_positions ip
JOIN (
  SELECT dc_id, sku, MAX(as_of_date) AS max_dt
  FROM main.mfg_agent_bricks_demo.inventory_positions
  GROUP BY dc_id, sku
) m
  ON m.dc_id = ip.dc_id
 AND m.sku = ip.sku
 AND m.max_dt = ip.as_of_date
ORDER BY ip.dc_id, ip.sku;
```
What is revenue and margin across suppliers, distributors, timeframe by month
```sql
WITH so AS (
  SELECT date_trunc('month', order_date) AS month, sku, distributor_id, region,
         SUM(units) AS units, SUM(units*unit_price) AS revenue
  FROM main.mfg_agent_bricks_demo.sales_orders
  GROUP BY 1, 2, 3, 4
),
cogs AS (
  SELECT sku, MAX_BY(unit_cogs, effective_date) AS unit_cogs
  FROM main.mfg_agent_bricks_demo.cogs_reference
  GROUP BY sku
),
supply_link AS (
  -- demo heuristic: dominant inbound supplier per SKU
  SELECT sku, supplier_id
  FROM (
    SELECT sku, supplier_id, ROW_NUMBER() OVER (PARTITION BY sku ORDER BY COUNT(*) DESC) AS r
    FROM main.mfg_agent_bricks_demo.supply_plan_inbound
    GROUP BY sku, supplier_id
  ) WHERE r=1
)
SELECT so.month, so.sku, sl.supplier_id, so.distributor_id, so.region,
       so.revenue,
       so.units * c.unit_cogs AS cogs,
       so.revenue - (so.units * c.unit_cogs) AS margin,
       CASE WHEN so.revenue>0 THEN (so.revenue - so.units*c.unit_cogs)/so.revenue ELSE NULL END AS margin_pct
FROM so
JOIN cogs c USING (sku)
LEFT JOIN supply_link sl USING (sku)
WHERE
  (COALESCE(:sku, '') = '' OR so.sku = :sku)
  AND (COALESCE(:region, '') = '' OR so.region = :region)
ORDER BY so.month, so.sku, so.distributor_id, so.region;
```
