# Agent Bricks Streamlit Chatbot

Production-ready chatbot application built with Databricks Agent Framework, featuring:
- **ResponsesAgent** pattern for scalable deployments
- **MLflow 3.x tracing** for full observability
- **User feedback collection** (👍/👎) linked to traces
- **Streaming responses** for improved UX
- **Local development** support with `.env` configuration

## Architecture

- `app.py`: Main Streamlit application with streaming chat interface
- `model_serving_utils.py`: ResponsesAgent implementation with MLflow tracing
- `app.yaml`: Databricks Apps deployment configuration

## Local Development

### Prerequisites

1. **Databricks CLI** configured with authentication
   ```bash
   databricks auth login --host https://your-workspace.cloud.databricks.com
   ```

2. **Python 3.10+** with pip

### Setup

1. **Install dependencies:**
   ```bash
   cd app/streamlit-chatbot-app
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**

   Create or update the `.env` file in the repository root (already exists):
   ```bash
   # .env file location: /path/to/repo/.env
   DATABRICKS_HOST=https://e2-demo-west.cloud.databricks.com
   DATABRICKS_CONFIG_PROFILE=e2-demo-west
   MLFLOW_TRACKING_URI=databricks
   MLFLOW_REGISTRY_URI=databricks-uc
   MLFLOW_EXPERIMENT_ID=1362705655702022

   # Set this to your deployed serving endpoint name
   SERVING_ENDPOINT=mas-3bfe8584-endpoint
   ```

3. **Run the app:**
   ```bash
   streamlit run app.py
   ```

4. **Access locally:**
   - Open browser to `http://localhost:8501`
   - Chat interface will load with your configured endpoint

### Local Testing Workflow

1. **Verify endpoint connectivity:**
   - App will fail at startup if `SERVING_ENDPOINT` is not accessible
   - Check that your Databricks CLI profile has proper permissions

2. **Test streaming responses:**
   - Type a question and observe token-by-token streaming
   - Check that full response appears after completion

3. **Test feedback collection:**
   - After each assistant response, click 👍 or 👎
   - Verify feedback is logged to MLflow (check experiment traces)

4. **View traces in MLflow:**
   - Navigate to your MLflow experiment: `https://<workspace>/ml/experiments/<MLFLOW_EXPERIMENT_ID>`
   - Each chat interaction creates a trace with full request/response
   - Feedback appears in the trace's assessments

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SERVING_ENDPOINT` | Yes | - | Name of Databricks serving endpoint to query |
| `MLFLOW_EXPERIMENT_ID` | No | `/Shared/streamlit-chatbot-app` | MLflow experiment for trace logging |
| `DATABRICKS_HOST` | Auto | From CLI config | Databricks workspace URL |
| `DATABRICKS_CONFIG_PROFILE` | Auto | `DEFAULT` | CLI profile name |

## Deployment to Databricks Apps

### Prerequisites

1. **Databricks bundle** configured (see `databricks.yml` in repo root)
2. **Serving endpoint** deployed and accessible
3. **Workspace permissions** for Apps deployment

### Deploy

```bash
# From repository root
databricks bundle deploy

# Follow Databricks Apps documentation to create app resource
# Reference the serving endpoint in app.yaml
```

### Key Differences: Local vs. Deployed

| Feature | Local Development | Databricks Apps |
|---------|------------------|-----------------|
| Environment | `.env` file | `app.yaml` + workspace resources |
| Authentication | CLI profile | Managed identity |
| User context | `local_user` | Real user from headers |
| Serving endpoint | Via `SERVING_ENDPOINT` env var | Via `app.yaml` resource reference |

## Features

### 1. ResponsesAgent Pattern

Uses MLflow's production-recommended `ResponsesAgent` class:
- Supports both streaming and non-streaming modes
- Built-in MLflow tracing with `@mlflow.trace()` decorators
- Compatible with MLflow Model Registry for deployment

### 2. MLflow Tracing

Every chat interaction generates a trace containing:
- Full conversation history (input)
- Model response (output)
- Latency metrics
- User feedback (when submitted)

Traces are viewable in MLflow Experiments UI.

### 3. User Feedback Collection

- 👍/👎 buttons appear after each assistant response
- Feedback links to the trace ID via `mlflow.log_feedback()`
- User ID captured from Streamlit context (or `local_user` in dev)
- Feedback appears in MLflow trace assessments for model improvement

### 4. Streaming Responses

- Token-by-token rendering using `predict_stream()`
- Cursor indicator (`▌`) during streaming
- Graceful error handling with user-friendly messages

## Troubleshooting

### "Unable to determine serving endpoint"
- Ensure `SERVING_ENDPOINT` is set in `.env`
- Verify endpoint exists: `databricks serving-endpoints get <endpoint-name>`

### "Authentication failed"
- Run `databricks auth login` to refresh credentials
- Check `DATABRICKS_CONFIG_PROFILE` matches your CLI profile

### "No traces appearing in MLflow"
- Verify `MLFLOW_EXPERIMENT_ID` points to valid experiment
- Check experiment permissions (you need WRITE access)
- Ensure `mlflow>=3.1.0` is installed

### Streaming not working
- Check endpoint type supports Responses API
- Verify event parsing logic in `app.py` (event types may vary by endpoint)

## Example Queries

Based on the Agent Bricks demo data:

**Supply Chain:**
- "What is the projected ending on hand and stockout risk?"
- "Show me inventory positions by DC and SKU"

**Finance:**
- "What is month-over-month revenue growth by SKU?"
- "Show monthly revenue, COGS, margin, and margin_pct by SKU"

**Multi-domain (via MAS agent):**
- "Which SKUs have the highest revenue and are at stockout risk?"

## Learn More

- [Databricks Agent Framework Docs](https://docs.databricks.com/aws/en/generative-ai/agent-framework/)
- [MLflow Tracing Guide](https://mlflow.org/docs/latest/tracing.html)
- [Streamlit Documentation](https://docs.streamlit.io/)
