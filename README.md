# Databricks Agent Bricks Demo Examples

End-to-end AI application built with Databricks, demonstrating a production-ready workflow from data setup to deployed chatbot.

## Overview

This repository showcases how to build intelligent agents using Databricks Agent Framework and Genie Spaces, culminating in a production Streamlit chatbot with MLflow tracing and user feedback collection.

**What you'll build:**
1. **Synthetic data assets** for supply chain and finance analytics
2. **Genie Spaces** for text-to-SQL conversational interfaces
3. **Agent Bricks** (agent instructions) for orchestration and knowledge retrieval
4. **Streamlit chatbot** deployed as a Databricks App with full observability

## Architecture Flow

```
Data Setup → Genie Spaces → Agent Bricks → Serving Endpoint → Streamlit App
    ↓            ↓              ↓               ↓                ↓
 UC Tables   Text-to-SQL   Instructions   MLflow Agent    User Interface
                                                             + Feedback
```

## Repository Structure

```
├── genie/                      # Genie Space configurations
│   ├── 00-setup-data-genie.ipynb    # Creates synthetic UC tables
│   ├── supply-chain-genie/          # Supply chain analytics Genie Space
│   └── finance-genie/               # Finance analytics Genie Space
│
├── agent_bricks/              # Agent instruction documents
│   ├── mas-genie-agent.md           # Master orchestration agent
│   └── sec-finance-agent.md         # SEC filings knowledge agent
│
├── app/streamlit-chatbot-app/ # Production Streamlit chatbot
│   ├── app.py                       # Main chatbot interface
│   ├── model_serving_utils.py       # ResponsesAgent with tracing
│   ├── app.yaml                     # Databricks Apps config
│   └── test_*.py                    # Validation test scripts
│
└── databricks.yml             # Databricks Asset Bundle config
```

## Quick Start (5 Steps)

### Step 1: Setup Data Assets

Create synthetic Unity Catalog tables for the demo:

```bash
# Run in Databricks notebook
genie/00-setup-data-genie.ipynb
```

**Creates:**
- Supply chain tables: `suppliers`, `inventory_positions`, `demand_forecast_daily`, `supply_plan_inbound`
- Finance tables: `product_master`, `distributors`, `cogs_reference`, `sales_orders`
- Contract documents: `contract_texts`

### Step 2: Create Genie Spaces

Build text-to-SQL conversational interfaces using Databricks Genie:

1. **Supply Chain Genie** - Answers questions about inventory, demand, and supply planning
2. **Finance Genie** - Analyzes revenue, margins, and financial performance

**Setup Instructions:**
- Follow Databricks documentation to create Genie Spaces
- Configure each Genie to access corresponding Unity Catalog tables
- Note the Genie Space URLs for agent configuration

### Step 3: Configure Agent Bricks

Agent instructions are in `agent_bricks/`:

- **`mas-genie-agent.md`**: Master agent that orchestrates between Supply Chain and Finance Genies
- **`sec-finance-agent.md`**: Knowledge agent for SEC filings and public disclosures

**Deploy agents:**
1. Create agents in Databricks using Agent Bricks
2. Upload instruction documents as agent configurations
3. Test and evaluate your agents
4. Deploy to serving endpoints for production use

**Important**: Note the experiment ID where the endpoint logs traces - you'll need this for the app.

### Step 4: Run Streamlit Chatbot

**Local Development:**

```bash
# Configure environment
cat > .env << EOF
DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
DATABRICKS_CONFIG_PROFILE=your-profile
MLFLOW_TRACKING_URI=databricks
MLFLOW_EXPERIMENT_ID=your-endpoint-experiment-id
SERVING_ENDPOINT=your-endpoint-name
EOF

# Load environment and run
source .env
cd app/streamlit-chatbot-app
streamlit run app.py
```

**Deploy to Databricks Apps:**

```bash
# Update app.yaml with your values
# Then deploy using Databricks Apps
```

See [`app/streamlit-chatbot-app/README.md`](app/streamlit-chatbot-app/README.md) for detailed setup instructions.

## Key Features

### 🎯 Multi-Domain Agent Orchestration
- Master agent routes questions to specialized Genie Spaces
- Seamless context preservation across domains
- Unified response synthesis

### 📊 Production-Ready Observability
- MLflow tracing for every request
- Single trace per request (no duplicates)
- Client request ID pattern for feedback association
- User feedback (👍/👎) linked to traces

### 🚀 Streaming Chat Experience
- Real-time token-by-token display
- Handles tool calls and agent reasoning
- Graceful error handling

### 🔧 Flexible Deployment
- Local development with `.env` configuration
- Databricks Apps for production with managed authentication
- Test scripts for validation

## Use Cases Demonstrated

**Supply Chain Analytics:**
- "What is the projected ending on hand and stockout risk?"
- "Show me inventory positions by DC and SKU"
- "What are the inbound supply plans?"

**Finance Analytics:**
- "What is month-over-month revenue growth by SKU?"
- "Show monthly revenue, COGS, margin, and margin_pct by SKU"
- "Analyze distributor performance by region"

**Multi-Domain (via MAS Agent):**
- "Which SKUs have the highest revenue and are at stockout risk?"
- "Show me financial performance for products with inventory issues"

**Knowledge Retrieval (SEC Agent):**
- "What did the company report about Q4 earnings?"
- "Summarize risks from the latest 10-K filing"

## Troubleshooting

### Duplicate Traces Issue
**Problem**: Seeing two traces per request (one under your user, one under service principal)

**Solution**: Ensure `MLFLOW_EXPERIMENT_ID` matches your serving endpoint's experiment:
```bash
databricks serving-endpoints get <endpoint> | grep experiment
```

### Authentication Issues
```bash
# Refresh Databricks authentication
databricks auth login --host https://your-workspace.cloud.databricks.com

# Verify profile
databricks auth profiles
```

### Testing & Validation
```bash
cd app/streamlit-chatbot-app

# Test tracing (verifies single trace creation)
python test_no_manual_tracing.py

# Test feedback (verifies client request ID pattern)
python test_client_request_id.py
```

## Learn More

- [Databricks Agent Framework](https://docs.databricks.com/aws/en/generative-ai/agent-framework/)
- [Genie Spaces Documentation](https://docs.databricks.com/aws/en/genie/)
- [MLflow Tracing Guide](https://mlflow.org/docs/latest/tracing.html)
- [Databricks Apps](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)
- [App README - Detailed Setup](app/streamlit-chatbot-app/README.md)

## Contributing

This is a demonstration repository. For issues or questions, please refer to Databricks documentation or contact your Databricks representative.

---

**Built with**: Databricks, MLflow, Streamlit, Genie Spaces, Agent Framework
