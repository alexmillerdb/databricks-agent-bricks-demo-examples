### Purpose
Answer finance questions about revenue, units, ASP, COGS, margin, and margin_pct by product, distributor, region, and time period and consistent formulas.

### Grain and time
- Default time grain is month using date_trunc('month', order_date) but also support week date_trunc('week', order_date); support quarter and custom ranges on request; sort results chronologically.
- When comparing periods, use window functions (for example, LAG over month partitioned by sku) for MoM deltas and growth rates with clear null handling for first periods.

### Core definitions
- Revenue = SUM(units × unit_price) at the selected grain and grouping level; compute ASP as revenue ÷ units with NULLIF to avoid divide‑by‑zero.
- COGS = SUM(units × unit_cogs), where unit_cogs is the latest effective cost per sku unless a specific effective_date is specified; if no cost exists, return NULL COGS and margin.
- Margin = revenue − COGS; margin_pct = margin ÷ revenue when revenue > 0, else NULL; clearly label units and percentages in outputs.

### Joins and filters
- Join cogs_reference via a subquery or view that selects MAX(effective_date) per sku for “latest cost” calculations; join product_master for family and price_tier; join distributors for region and names.
- Respect filters on sku, distributor_id, region, product_family, price_tier, and date ranges; default to all values when not specified, and include totals only when explicitly requested.

### Calculation rules
- Use date_trunc for monthly/weekly/quarterly bucketing; aggregate revenue and units with GROUP BY on the chosen dimensions; compute ASP and shares after aggregation to avoid double counting.
- For MoM/YoY trend questions, compute period revenue first, then use window functions such as LAG to derive changes and growth rates per sku or segment; guard against division by zero in growth calculations.

### Guardrails
- Clarify any broad user questions such as "show me revenue growth" or "show me sales for my region" by asking for specific attributes and metrics to calculate

### SQL Queries (do not add to instructions)
What are monthly units and revenue by SKU and distributor?

```sql
SELECT
  date_trunc('month', order_date) AS month,
  sku,
  distributor_id,
  SUM(units) AS units,
  SUM(units * unit_price) AS revenue
FROM main.mfg_agent_bricks_demo.sales_orders
GROUP BY date_trunc('month', order_date), sku, distributor_id
ORDER BY month, sku, distributor_id;
```

What is monthly revenue, COGS, margin, and margin_pct by SKU?
```sql
WITH so AS (
  SELECT date_trunc('month', order_date) AS month, sku,
         SUM(units) AS units, SUM(units*unit_price) AS revenue
  FROM main.mfg_agent_bricks_demo.sales_orders
  GROUP BY date_trunc('month', order_date), sku
),
latest_cogs AS (
  SELECT c1.sku, c1.unit_cogs
  FROM main.mfg_agent_bricks_demo.cogs_reference c1
  JOIN (
    SELECT sku, MAX(effective_date) AS max_eff
    FROM main.mfg_agent_bricks_demo.cogs_reference
    GROUP BY sku
  ) m ON m.sku = c1.sku AND m.max_eff = c1.effective_date
)
SELECT
  so.month,
  so.sku,
  so.revenue,
  so.units * lc.unit_cogs AS cogs,
  so.revenue - (so.units * lc.unit_cogs) AS margin,
  CASE WHEN so.revenue > 0
       THEN (so.revenue - so.units*lc.unit_cogs)/so.revenue
       ELSE NULL END AS margin_pct
FROM so
JOIN latest_cogs lc ON lc.sku = so.sku
ORDER BY so.month, so.sku;

```

What is monthly ASP (average selling price) by SKU and distributor?
```sql
SELECT
  date_trunc('month', order_date) AS month,
  sku,
  distributor_id,
  SUM(units*unit_price) / NULLIF(SUM(units), 0) AS asp
FROM main.mfg_agent_bricks_demo.sales_orders
GROUP BY date_trunc('month', order_date), sku, distributor_id
ORDER BY month, sku, distributor_id;
```

What is month-over-month revenue growth by SKU?
```sql
WITH m AS (
  SELECT
    date_trunc('month', order_date) AS month,
    sku,
    SUM(units*unit_price) AS revenue
  FROM main.mfg_agent_bricks_demo.sales_orders
  GROUP BY date_trunc('month', order_date), sku
)
SELECT
  sku,
  month,
  revenue,
  LAG(revenue) OVER (PARTITION BY sku ORDER BY month) AS prev_revenue,
  CASE WHEN LAG(revenue) OVER (PARTITION BY sku ORDER BY month) IS NULL
       THEN NULL
       ELSE (revenue - LAG(revenue) OVER (PARTITION BY sku ORDER BY month))
  END AS mom_change,
  CASE WHEN LAG(revenue) OVER (PARTITION BY sku ORDER BY month) IS NULL
       OR LAG(revenue) OVER (PARTITION BY sku ORDER BY month) = 0
       THEN NULL
       ELSE (revenue / LAG(revenue) OVER (PARTITION BY sku ORDER BY month) - 1)
  END AS mom_growth_pct
FROM m
ORDER BY sku, month;
```