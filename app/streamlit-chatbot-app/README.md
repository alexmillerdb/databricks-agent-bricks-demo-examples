# Agent Bricks Streamlit Chatbot

Production-ready chatbot application built with Databricks Agent Framework, featuring:
- **ResponsesAgent** pattern for scalable deployments
- **MLflow tracing** with client request ID for feedback association
- **User feedback collection** (👍/👎) linked to traces
- **Streaming responses** with real-time token display
- **Dual deployment**: Local development and Databricks Apps

## Architecture

- `app.py`: Main Streamlit application with streaming chat interface and feedback UI
- `model_serving_utils.py`: ResponsesAgent implementation with client request ID tracking
- `app.yaml`: Databricks Apps deployment configuration
- `test_*.py`: Test scripts for validating tracing and feedback functionality

## Key Design Decisions

### Tracing Strategy
- **No manual client-side tracing**: Avoids duplicate traces
- **Serving endpoint auto-tracing**: Endpoint creates traces automatically
- **Client request ID tagging**: Used to associate feedback with the correct trace
- **Single trace per request**: Eliminates confusion between user and service principal traces

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

   Create or update the `.env` file in the **repository root** (two levels up):
   ```bash
   # .env file location: ../../.env
   DATABRICKS_HOST=https://your-workspace.cloud.databricks.com
   DATABRICKS_CONFIG_PROFILE=your-profile-name
   MLFLOW_TRACKING_URI=databricks
   MLFLOW_REGISTRY_URI=databricks-uc
   MLFLOW_EXPERIMENT_ID=your-experiment-id  # Must match serving endpoint's experiment

   # Set this to your deployed serving endpoint name
   SERVING_ENDPOINT=your-endpoint-name
   ```

   **Important**: `MLFLOW_EXPERIMENT_ID` must match the experiment ID configured in your serving endpoint to avoid duplicate traces.

3. **Run the app:**
   ```bash
   # Load environment variables
   source ../../.env

   # Run Streamlit
   streamlit run app.py
   ```

4. **Access locally:**
   - Open browser to `http://localhost:8501`
   - Chat interface will load with your configured endpoint
   - MLflow traces will be logged to Databricks (not local filesystem)

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

| Variable | Required | Description |
|----------|----------|-------------|
| `SERVING_ENDPOINT` | **Yes** | Name of Databricks serving endpoint to query |
| `MLFLOW_EXPERIMENT_ID` | **Yes** | MLflow experiment for trace logging (**must match endpoint's experiment**) |
| `DATABRICKS_CONFIG_PROFILE` | **Yes** | Databricks CLI profile name for authentication |
| `DATABRICKS_HOST` | Optional | Databricks workspace URL (inferred from profile if not set) |
| `MLFLOW_TRACKING_URI` | Optional | Set to `databricks` to use Databricks MLflow tracking |
| `MLFLOW_REGISTRY_URI` | Optional | Set to `databricks-uc` for Unity Catalog model registry |

### Testing Scripts

Run tests to verify tracing and feedback functionality:

```bash
# Load environment
source ../../.env

# Test that only one trace is created (no duplicates)
python test_no_manual_tracing.py

# Test client request ID and feedback logging
python test_client_request_id.py
```

**What the tests verify:**
- Only ONE trace is created per query (serving endpoint trace only)
- Client request ID is generated and stored
- Feedback can be logged and associated with the correct trace
- Traces are visible in Databricks MLflow experiment

## Deployment to Databricks Apps

### Understanding app.yaml

The `app.yaml` file configures how the app runs in Databricks Apps:

```yaml
command: ["streamlit", "run", "app.py"]

env:
  - name: STREAMLIT_BROWSER_GATHER_USAGE_STATS
    value: "false"
  - name: "SERVING_ENDPOINT"
    valueFrom: "serving-endpoint"  # References Databricks resource
  - name: "MLFLOW_TRACKING_URI"
    value: "databricks"
  - name: "MLFLOW_EXPERIMENT_ID"
    value: "3040165994661313"  # Your MLflow experiment ID
```

**Key configuration points:**
1. **SERVING_ENDPOINT**: Uses `valueFrom: "serving-endpoint"` to reference a Databricks workspace resource
2. **MLFLOW_EXPERIMENT_ID**: Must match the experiment your serving endpoint logs to
3. **MLFLOW_TRACKING_URI**: Set to `databricks` to use workspace MLflow tracking

### Deploy Steps

1. **Ensure your serving endpoint is deployed:**
   ```bash
   databricks serving-endpoints get <your-endpoint-name>
   ```

2. **Update app.yaml with your values:**
   - Set `MLFLOW_EXPERIMENT_ID` to match your endpoint's experiment
   - Verify `valueFrom: "serving-endpoint"` matches your resource name

3. **Deploy using Databricks Apps:**
   ```bash
   # Follow Databricks Apps documentation for deployment
   # The app will use service principal authentication automatically
   ```

### Key Differences: Local vs. Deployed

| Feature | Local Development | Databricks Apps |
|---------|------------------|-----------------|
| Environment | `.env` file from repo root | `app.yaml` configuration |
| Authentication | CLI profile (your user) | Service principal (managed identity) |
| User context | `local_user` fallback | Real user from Databricks headers |
| MLflow tracking | Databricks (via CLI auth) | Databricks (via service principal) |
| Trace ownership | Your user | Service principal (endpoint's identity) |

## Features

### 1. Single-Trace Architecture

**Problem solved**: Eliminates duplicate traces when client and serving endpoint both create traces.

**How it works**:
- Serving endpoint automatically creates traces (no client-side tracing)
- Client generates unique `client_request_id` for each query
- After streaming, client tags the endpoint's trace with `client_request_id`
- Feedback function searches for trace by `client_request_id` tag
- Result: Only ONE trace per request, with proper feedback association

### 2. ResponsesAgent Pattern

Uses Databricks' `ResponsesAgent` class for production deployments:
- Supports streaming via `predict_stream()` generator
- No manual MLflow span creation (avoids duplicate traces)
- Compatible with Databricks serving endpoints using Responses API

### 3. MLflow Tracing & Feedback

**Trace flow:**
1. User sends query → Serving endpoint creates trace automatically
2. Client generates `client_request_id` and tags the trace
3. User clicks 👍/👎 → App searches for trace by `client_request_id`
4. Feedback logged to correct trace via `mlflow.log_feedback()`

**Trace contents:**
- Full conversation history
- Model response with streaming events
- Client request ID (for feedback lookup)
- User feedback assessments

### 4. Streaming Responses

- Real-time token-by-token display
- Handles different event types: `response.output_text.delta`, `response.output_item.done`, `function_call`, etc.
- Filters problematic events (e.g., `function_call_output`) to avoid Pydantic warnings
- Graceful error handling with user-friendly messages

## Troubleshooting

### Seeing duplicate traces (two traces per request)

**Symptom**: Two traces appear in MLflow for each query - one under your user, one under service principal.

**Cause**: `MLFLOW_EXPERIMENT_ID` doesn't match the serving endpoint's experiment.

**Fix**:
1. Find your endpoint's experiment ID:
   ```bash
   databricks serving-endpoints get <endpoint-name> | grep experiment
   ```
2. Update `.env` file with matching `MLFLOW_EXPERIMENT_ID`
3. Restart the app

### "Unable to determine serving endpoint"
- Ensure `SERVING_ENDPOINT` is set in `.env`
- Verify endpoint exists: `databricks serving-endpoints get <endpoint-name>`
- Check endpoint is using Responses API (not legacy chat API)

### "Authentication failed"
- Run `databricks auth login --host <workspace-url>` to refresh credentials
- Check `DATABRICKS_CONFIG_PROFILE` matches your CLI profile
- Verify profile exists: `databricks auth profiles`

### "No traces appearing in MLflow"
- Verify `MLFLOW_EXPERIMENT_ID` points to valid experiment in your workspace
- Check experiment permissions (you need WRITE access)
- Ensure `MLFLOW_TRACKING_URI=databricks` is set
- Run test scripts to verify: `python test_no_manual_tracing.py`

### Feedback not associating with traces
- Check that `client_request_id` is being generated (see logs)
- Verify traces are tagged: Look for `client_request_id` tag in MLflow UI
- Ensure feedback search looks in correct experiment
- Run `python test_client_request_id.py` to validate

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
