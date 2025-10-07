"""
Test the updated approach without manual tracing in predict_stream.
Verify that only ONE trace is created (by the serving endpoint).
"""
import os
import mlflow
from model_serving_utils import get_agent
from mlflow.types.responses import ResponsesAgentRequest
from mlflow.tracking import MlflowClient
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up Databricks MLflow tracking
os.environ["DATABRICKS_CONFIG_PROFILE"] = "e2-demo-west"
SERVING_ENDPOINT = os.environ.get("SERVING_ENDPOINT", "mas-3bfe8584-endpoint")
EXPERIMENT_ID = os.environ.get("MLFLOW_EXPERIMENT_ID", "3040165994661313")

# Configure MLflow to use Databricks tracking server
mlflow.set_tracking_uri("databricks")
mlflow.set_experiment(experiment_id=EXPERIMENT_ID)

print(f"MLflow Tracking URI: {mlflow.get_tracking_uri()}")
print(f"MLflow Experiment ID: {EXPERIMENT_ID}")
print(f"Serving Endpoint: {SERVING_ENDPOINT}\n")

print(f"Testing NO manual tracing approach with endpoint: {SERVING_ENDPOINT}\n")
print("="*80)

# Get initial trace count
client = MlflowClient()
initial_traces = client.search_traces(
    experiment_ids=[EXPERIMENT_ID],
    max_results=10,
    order_by=["timestamp DESC"]
)
initial_count = len(initial_traces)
print(f"Initial trace count: {initial_count}")

# Make a query
print("\n[TEST] Query endpoint without manual tracing")
print("-"*80)

agent = get_agent(SERVING_ENDPOINT)
test_request = ResponsesAgentRequest(
    input=[{"role": "user", "content": "What is 9+10?"}]
)

try:
    full_response = ""
    for event in agent.predict_stream(test_request):
        if hasattr(event, 'delta') and event.delta:
            full_response += event.delta

    client_request_id = agent.get_last_client_request_id()
    print(f"✓ Client request ID: {client_request_id}")
    print(f"Response preview: {full_response[:100]}...")

    # Wait a moment for trace to be indexed
    time.sleep(2)

    # Check how many NEW traces were created
    new_traces = client.search_traces(
        experiment_ids=[EXPERIMENT_ID],
        max_results=10,
        order_by=["timestamp DESC"]
    )
    new_count = len([t for t in new_traces if t not in initial_traces])

    print(f"\n📊 Trace Analysis:")
    print(f"  Traces before query: {initial_count}")
    print(f"  New traces created: {new_count}")

    if new_count == 1:
        print(f"\n✓ SUCCESS! Only ONE trace was created (no duplicate)")
        print(f"  This means we eliminated the manual client-side trace!")
    elif new_count == 0:
        print(f"\n⚠ WARNING: No new trace was created")
        print(f"  The serving endpoint might not be auto-tracing")
    else:
        print(f"\n✗ PROBLEM: {new_count} traces were created")
        print(f"  We're still getting duplicate traces")

        # Show the traces
        print(f"\n  Recent traces:")
        for i, trace in enumerate(new_traces[:new_count]):
            print(f"    {i+1}. {trace.info.trace_id}")
            print(f"       Name: {trace.info.tags.get('mlflow.traceName', 'N/A')}")
            if hasattr(trace.info, 'client_request_id'):
                print(f"       Client Request ID: {trace.info.client_request_id}")

except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
