# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository demonstrates end-to-end AI application building on Databricks, showcasing three components:
1. **Genie Spaces**: Text-to-SQL conversational interfaces for supply chain and finance analytics
2. **Agent Bricks**: Knowledge assistants using retrieval and orchestration patterns
3. **Custom Front-end**: Streamlit chatbot application deployed as a Databricks app

## Project Structure

- `genie/`: Genie Space configurations and setup notebooks
  - Supply Chain Genie: Demand vs. supply reconciliation, projected EOH, stockout risk
  - Finance Genie: Revenue, margin, ASP analytics by product/distributor/region
  - `00-setup-data-genie.ipynb`: Creates synthetic UC tables for demo data

- `agent_bricks/`: Agent instruction documents
  - `mas-genie-agent.md`: Master agent orchestrating Supply Chain & Finance Genie Spaces
  - `sec-finance-agent.md`: Knowledge assistant for SEC filings and public company disclosures

- `app/streamlit-chatbot-app/`: Databricks app front-end
  - `app.py`: Main Streamlit chatbot interface
  - `model_serving_utils.py`: Helper functions for querying Databricks serving endpoints
  - `app.yaml`: App configuration with serving endpoint reference

## Databricks Bundle Configuration

- `databricks.yml`: Asset bundle definition for deployment
- Default target: `dev` pointing to `https://e2-demo-west.cloud.databricks.com`
- Bundle name: `databricks-agent-bricks-demo-examples`

## Data Schema

All tables live in Unity Catalog under catalog `main`, schema `mfg_agent_bricks_demo`:

**Supply Chain Tables:**
- `suppliers`: Supplier master (tier, country)
- `inventory_positions`: Daily on-hand & safety stock by DC/SKU
- `demand_forecast_daily`: Daily demand forecast by SKU/region/DC
- `supply_plan_inbound`: Planned inbound shipments with PO, ETA, units

**Finance Tables:**
- `product_master`: SKU metadata (family, launch date, price tier)
- `distributors`: Distributor dimension (region, channel)
- `cogs_reference`: Unit COGS by SKU and effective date
- `sales_orders`: Sales transactions with units and unit price

**Contracts:**
- `contract_texts`: Supplier/distributor agreement narratives (Markdown/HTML)

## Common Commands

### Deploy Databricks Bundle
```bash
databricks bundle deploy
```

### Run Streamlit App Locally
Requires `SERVING_ENDPOINT` environment variable set to your serving endpoint name:
```bash
cd app/streamlit-chatbot-app
export SERVING_ENDPOINT=your-endpoint-name
streamlit run app.py
```

### Setup Demo Data
Execute `genie/00-setup-data-genie.ipynb` in Databricks to generate synthetic tables.

## Key Patterns

**Genie Spaces**: Designed for SQL-based analytics with specific calculation rules (e.g., latest COGS via `MAX(effective_date)`, LAG for MoM trends, projected EOH via cumulative window functions).

**Agent Orchestration**: The MAS Genie agent routes multi-domain questions to specialized Genie Spaces, preserves context, and synthesizes unified answers.

**SEC Finance Agent**: Retrieves and cites SEC filings (10-K/10-Q), earnings releases, and transcripts with strict attribution guidelines (company, form type, period, section).

**App Integration**: Streamlit app queries Databricks serving endpoints via REST API; only supports chat-completion-compatible endpoints.
