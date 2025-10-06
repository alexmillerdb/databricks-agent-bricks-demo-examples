import os
from typing import Generator
from databricks.sdk import WorkspaceClient
import mlflow
from mlflow.entities.span import SpanType
from mlflow.pyfunc import ResponsesAgent
from mlflow.types.responses import (
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)


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

    @mlflow.trace(span_type=SpanType.AGENT)
    def predict_stream(
        self, request: ResponsesAgentRequest
    ) -> Generator[ResponsesAgentStreamEvent, None, None]:
        """
        Query the endpoint with streaming enabled.

        Args:
            request: ResponsesAgentRequest containing the conversation input

        Yields:
            ResponsesAgentStreamEvent objects as tokens arrive
        """
        for event in self.client.responses.create(
            input=request.input, stream=True, model=self.model
        ):
            # Yield the raw event object directly without conversion
            # The event is already compatible with ResponsesAgentStreamEvent
            yield event

    @mlflow.trace(span_type=SpanType.AGENT)
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
