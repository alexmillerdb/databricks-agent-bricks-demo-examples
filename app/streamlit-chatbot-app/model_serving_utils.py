from typing import Generator, Optional
from databricks.sdk import WorkspaceClient
import mlflow
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)
import logging
import uuid

logger = logging.getLogger(__name__)


class SimpleResponsesAgent(ResponsesAgent):
    """
    Production-ready Responses Agent for querying Databricks serving endpoints.

    Supports both streaming and non-streaming modes with MLflow tracing.
    Uses client_request_id for reliable feedback tracking across traces.
    """

    def __init__(self, model: str):
        """
        Initialize the ResponsesAgent.

        Args:
            model: The name of the Databricks serving endpoint to query
        """
        self.client = WorkspaceClient().serving_endpoints.get_open_ai_client()
        self.model = model
        self.current_client_request_id: Optional[str] = None

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """
        Query the endpoint with streaming enabled.

        Args:
            request: ResponsesAgentRequest containing the conversation input

        Yields:
            ResponsesAgentStreamEvent objects as tokens arrive

        Note: No manual tracing - relies on serving endpoint's automatic tracing.
        Client request ID is generated and stored for feedback tracking.
        """
        # Generate unique client request ID for this request
        client_request_id = f"req-{uuid.uuid4().hex[:8]}"
        self.current_client_request_id = client_request_id
        logger.info(f"Generated client request ID: {client_request_id}")

        try:
            event_count = 0

            for event in self.client.responses.create(
                input=request.input, stream=True, model=self.model
            ):
                event_count += 1

                # Filter out problematic function_call_output events to avoid Pydantic warnings
                if hasattr(event, 'item') and hasattr(event.item, 'type'):
                    if event.item.type == 'function_call_output':
                        # Log the handoff but don't yield the problematic event
                        logger.debug(f"Skipping function_call_output event: {getattr(event.item, 'output', '')}")
                        continue

                # Yield the raw event object directly without conversion
                yield event

            logger.info(f"Completed streaming {event_count} events for client_request_id: {client_request_id}")

        except Exception as e:
            logger.error(f"Error in predict_stream: {e}")
            raise

    def get_last_client_request_id(self) -> Optional[str]:
        """Get the client request ID from the last predict_stream call."""
        return self.current_client_request_id

    def predict(
        self, request: ResponsesAgentRequest
    ) -> ResponsesAgentResponse:
        """
        Query the endpoint without streaming (synchronous response).

        Args:
            request: ResponsesAgentRequest containing the conversation input

        Returns:
            ResponsesAgentResponse with the complete response
        """
        response = self.client.responses.create(
            input=request.input, stream=False, model=self.model
        )
        # Return the raw response object directly
        return response


def get_agent(endpoint_name: str) -> SimpleResponsesAgent:
    """
    Factory function to create a ResponsesAgent instance.

    Args:
        endpoint_name: Name of the Databricks serving endpoint

    Returns:
        SimpleResponsesAgent instance configured for the endpoint
    """
    return SimpleResponsesAgent(model=endpoint_name)


def log_user_feedback(client_request_id: str, thumbs_up: bool, comment: str = "", user_id: str = "unknown", experiment_id: str = None):
    """
    Log user feedback for a specific trace to MLflow using client request ID.

    Args:
        client_request_id: The client request ID to find the trace
        thumbs_up: True for positive feedback, False for negative
        comment: Optional text comment from the user
        user_id: User identifier (email, username, etc.)
        experiment_id: MLflow experiment ID to search in (uses MLFLOW_EXPERIMENT_ID env var if not provided)

    Returns:
        True if feedback was logged successfully, False otherwise
    """
    from mlflow.entities.assessment import AssessmentSource, AssessmentSourceType
    from mlflow.tracking import MlflowClient
    import os

    try:
        logger.info(f"Attempting to log feedback for client_request_id: {client_request_id}, thumbs_up: {thumbs_up}, user_id: {user_id}")

        # Get experiment ID from env if not provided
        if experiment_id is None:
            experiment_id = os.environ.get("MLFLOW_EXPERIMENT_ID", "0")  # Default to experiment 0
            logger.info(f"Using experiment_id: {experiment_id}")

        # Search for trace using client_request_id
        # Note: The Databricks docs show using filter_string with 'attributes.client_request_id',
        # but this doesn't work in local MLflow (only in Databricks-hosted MLflow).
        # We search recent traces and filter manually instead.
        client = MlflowClient()

        # Search recent traces and filter manually by client_request_id
        recent_traces = client.search_traces(
            experiment_ids=[experiment_id],
            max_results=50,  # Search recent traces
            order_by=["timestamp DESC"]
        )

        # Find matching trace by checking tags
        matching_trace = None
        for trace in recent_traces:
            # Check both trace.info.client_request_id (from mlflow.update_current_trace)
            # and trace.info.tags (from mlflow.update_trace with tags)
            if hasattr(trace.info, 'client_request_id') and trace.info.client_request_id == client_request_id:
                matching_trace = trace
                break
            elif hasattr(trace.info, 'tags') and trace.info.tags.get('client_request_id') == client_request_id:
                matching_trace = trace
                break

        if not matching_trace:
            logger.error(f"No trace found for client_request_id: {client_request_id} in experiment {experiment_id}")
            return False

        trace_id = matching_trace.info.trace_id
        logger.info(f"Found trace_id: {trace_id} for client_request_id: {client_request_id}")

        mlflow.log_feedback(
            trace_id=trace_id,
            name="user_feedback",
            value=thumbs_up,
            rationale=comment if comment else ("Positive feedback" if thumbs_up else "Negative feedback"),
            source=AssessmentSource(
                source_type=AssessmentSourceType.HUMAN,
                source_id=user_id
            ),
        )

        logger.info(f"Successfully logged feedback for trace_id: {trace_id} (client_request_id: {client_request_id})")
        return True

    except Exception as e:
        logger.error(f"Failed to log feedback for client_request_id {client_request_id}: {e}", exc_info=True)
        return False
