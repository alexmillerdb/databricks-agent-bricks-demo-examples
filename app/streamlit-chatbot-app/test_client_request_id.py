"""
Test the updated model_serving_utils with client_request_id approach.
This validates that:
1. Client request IDs are generated and tagged to traces
2. Traces can be found by client_request_id
3. Feedback can be logged successfully
"""
import os
import time
import mlflow
from model_serving_utils import get_agent, log_user_feedback
from mlflow.types.responses import ResponsesAgentRequest
from mlflow.tracking import MlflowClient
import logging

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

print(f"Testing client_request_id approach with endpoint: {SERVING_ENDPOINT}\n")
print("="*80)

# Test 1: Generate a request and capture client_request_id
print("\n[TEST 1] Query endpoint and capture client_request_id")
print("-"*80)

agent = get_agent(SERVING_ENDPOINT)
test_request = ResponsesAgentRequest(
    input=[{"role": "user", "content": "What is 7+8?"}]
)

try:
    full_response = ""
    for event in agent.predict_stream(test_request):
        if hasattr(event, 'delta') and event.delta:
            full_response += event.delta

    client_request_id = agent.get_last_client_request_id()
    print(f"✓ Client request ID: {client_request_id}")
    print(f"Response preview: {full_response[:100]}...")

    if not client_request_id:
        print("✗ FAILED: No client_request_id captured!")
        exit(1)

except Exception as e:
    print(f"✗ FAILED: {e}")
    exit(1)

# Test 2: Search for trace by client_request_id
print("\n[TEST 2] Search for trace by client_request_id")
print("-"*80)

try:
    # Give MLflow a moment to index the trace
    print("Waiting 3 seconds for trace to be indexed...")
    time.sleep(3)

    # Use the configured experiment ID
    client = MlflowClient()

    # Search recent traces and filter manually
    recent_traces = client.search_traces(
        experiment_ids=[EXPERIMENT_ID],
        max_results=50,
        order_by=["timestamp DESC"]
    )

    # Find matching trace
    matching_trace = None
    for trace in recent_traces:
        if hasattr(trace.info, 'client_request_id') and trace.info.client_request_id == client_request_id:
            matching_trace = trace
            break

    if matching_trace:
        print(f"✓ Found trace!")
        print(f"  Trace ID: {matching_trace.info.trace_id}")
        print(f"  Client request ID from trace: {matching_trace.info.client_request_id}")
    else:
        print(f"✗ FAILED: No trace found for client_request_id: {client_request_id}")
        print("\nDebugging - searching for recent traces:")
        for i, t in enumerate(recent_traces[:5]):
            print(f"\n  Trace {i+1}:")
            print(f"    Trace ID: {t.info.trace_id}")
            print(f"    Client request ID: {getattr(t.info, 'client_request_id', 'N/A')}")
        exit(1)

except Exception as e:
    print(f"✗ FAILED: Error searching for trace: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 3: Log feedback using client_request_id
print("\n[TEST 3] Log feedback using client_request_id")
print("-"*80)

try:
    success = log_user_feedback(
        client_request_id=client_request_id,
        thumbs_up=True,
        comment="Test feedback from test script",
        user_id="test_user@example.com"
    )

    if success:
        print("✓ Feedback logged successfully!")

        # Verify feedback was attached - search again for the trace
        recent_traces = client.search_traces(
            experiment_ids=[EXPERIMENT_ID],
            max_results=50,
            order_by=["timestamp DESC"]
        )

        matching_trace = None
        for trace in recent_traces:
            if hasattr(trace.info, 'client_request_id') and trace.info.client_request_id == client_request_id:
                matching_trace = trace
                break

        if matching_trace and hasattr(matching_trace.data, 'assessments') and matching_trace.data.assessments:
            print(f"  Assessments found: {len(matching_trace.data.assessments)}")
            for assessment in matching_trace.data.assessments:
                print(f"    - {assessment.name}: {assessment.value}")
        else:
            print("  Note: Assessments may take a moment to appear in search results")
    else:
        print("✗ FAILED: Feedback logging returned False")
        exit(1)

except Exception as e:
    print(f"✗ FAILED: Error logging feedback: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "="*80)
print("SUCCESS! All tests passed.")
print("="*80)
print("\nKey findings:")
print(f"1. Client request ID generated: {client_request_id}")
print(f"2. Trace found by client_request_id: ✓")
print(f"3. Feedback logged successfully: ✓")
print("\nThis approach should resolve the dual-trace issue!")
print("Next: Update app.py to use get_last_client_request_id() instead of get_last_trace_id()")
