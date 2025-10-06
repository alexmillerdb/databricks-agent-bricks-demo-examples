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

logger = logging.getLogger(__name__)


class SimpleResponsesAgent(ResponsesAgent):
    """
    Production-ready Responses Agent for querying Databricks serving endpoints.

    Supports both streaming and non-streaming modes with MLflow tracing.
    """

    def __init__(self, model: str):
        """
        Initialize the ResponsesAgent.

        Args:
            model: The name of the Databricks serving endpoint to query
        """
        self.client = WorkspaceClient().serving_endpoints.get_open_ai_client()
        self.model = model
        self.current_trace_id: Optional[str] = None

    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """
        Query the endpoint with streaming enabled.

        Args:
            request: ResponsesAgentRequest containing the conversation input

        Yields:
            ResponsesAgentStreamEvent objects as tokens arrive

        Note: Uses manual span tracing to avoid Pydantic serialization issues with streaming events.
        """
        # Start manual span with minimal metadata to avoid serialization issues
        with mlflow.start_span(name="responses_agent_stream") as span:
            # Store the trace ID from the span
            self.current_trace_id = span.request_id
            logger.info(f"Started manual trace: {self.current_trace_id}")

            try:
                response_text = []
                event_count = 0

                for event in self.client.responses.create(
                    input=request.input, stream=True, model=self.model
                ):
                    event_count += 1

                    # Collect text deltas for trace output
                    if hasattr(event, 'delta') and event.delta:
                        response_text.append(event.delta)

                    # Yield the raw event object directly without conversion
                    yield event

                # Set span attributes with simple values (avoiding complex object serialization)
                span.set_attribute("event_count", event_count)
                span.set_attribute("model", self.model)
                span.set_attribute("response_preview", "".join(response_text)[:500] if response_text else "")
                logger.info(f"Completed trace successfully: {self.current_trace_id}")

            except Exception as e:
                # Set error status on span
                span.set_status("ERROR")
                span.set_attribute("error", str(e))
                logger.error(f"Error in predict_stream: {e}")
                raise

    def get_last_trace_id(self) -> Optional[str]:
        """Get the trace ID from the last predict_stream call."""
        return self.current_trace_id

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


def log_user_feedback(trace_id: str, thumbs_up: bool, comment: str = "", user_id: str = "unknown"):
    """
    Log user feedback for a specific trace to MLflow.

    Args:
        trace_id: The MLflow trace ID to attach feedback to
        thumbs_up: True for positive feedback, False for negative
        comment: Optional text comment from the user
        user_id: User identifier (email, username, etc.)
    """
    from mlflow.entities.assessment import AssessmentSource, AssessmentSourceType

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
