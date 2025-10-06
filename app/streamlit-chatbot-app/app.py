import logging
import os
import streamlit as st
from dotenv import load_dotenv
import mlflow
from mlflow.types.responses import ResponsesAgentRequest
from model_serving_utils import get_agent, log_user_feedback

# Load .env file for local development (ignored when deployed to Databricks Apps)
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure environment variable is set correctly
SERVING_ENDPOINT = os.getenv('SERVING_ENDPOINT')
assert SERVING_ENDPOINT, \
    ("Unable to determine serving endpoint to use for chatbot app. If developing locally, "
     "set the SERVING_ENDPOINT environment variable in .env file. If "
     "deploying to a Databricks app, include a serving endpoint resource named "
     "'serving_endpoint' with CAN_QUERY permissions, as described in "
     "https://docs.databricks.com/aws/en/generative-ai/agent-framework/chat-app#deploy-the-databricks-app")

# Configure MLflow experiment for tracing
MLFLOW_EXPERIMENT_ID = os.getenv('MLFLOW_EXPERIMENT_ID')
if MLFLOW_EXPERIMENT_ID:
    mlflow.set_experiment(experiment_id=MLFLOW_EXPERIMENT_ID)
    logger.info(f"MLflow experiment set to ID: {MLFLOW_EXPERIMENT_ID}")
else:
    # Fallback to experiment name if ID not provided
    mlflow.set_experiment("/Shared/streamlit-chatbot-app")
    logger.info("MLflow experiment set to /Shared/streamlit-chatbot-app")

# Initialize ResponsesAgent
agent = get_agent(SERVING_ENDPOINT)


def get_user_info():
    """Extract user information from Streamlit context headers."""
    headers = st.context.headers
    return dict(
        user_name=headers.get("X-Forwarded-Preferred-Username", "local_user"),
        user_email=headers.get("X-Forwarded-Email", "local@example.com"),
        user_id=headers.get("X-Forwarded-User", "local_user"),
    )


user_info = get_user_info()

# Streamlit app
if "visibility" not in st.session_state:
    st.session_state.visibility = "visible"
    st.session_state.disabled = False

if "feedback_submitted" not in st.session_state:
    st.session_state.feedback_submitted = {}

st.title("🧱 Agent Bricks Chatbot")

st.markdown(
    f"**Endpoint:** `{SERVING_ENDPOINT}` | **User:** {user_info['user_name']}"
)

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if "trace_ids" not in st.session_state:
    st.session_state.trace_ids = []

# Display chat messages from history on app rerun
for idx, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        # Show feedback buttons for assistant messages
        if message["role"] == "assistant" and idx < len(st.session_state.trace_ids):
            trace_id = st.session_state.trace_ids[idx // 2]  # Each Q&A pair has one trace

            # Only show buttons if feedback hasn't been submitted for this message
            if trace_id not in st.session_state.feedback_submitted:
                col1, col2 = st.columns([1, 10])
                with col1:
                    if st.button("👍", key=f"thumbs_up_{idx}"):
                        log_user_feedback(trace_id, True, user_id=user_info["user_id"])
                        st.session_state.feedback_submitted[trace_id] = "positive"
                        st.rerun()
                with col2:
                    if st.button("👎", key=f"thumbs_down_{idx}"):
                        log_user_feedback(trace_id, False, user_id=user_info["user_id"])
                        st.session_state.feedback_submitted[trace_id] = "negative"
                        st.rerun()
            else:
                feedback_type = st.session_state.feedback_submitted[trace_id]
                st.caption(f"✓ Feedback submitted: {feedback_type}")

# Accept user input
if prompt := st.chat_input("Ask me anything about your supply chain or finance data..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Display user message in chat message container
    with st.chat_message("user"):
        st.markdown(prompt)

    # Display assistant response in chat message container
    with st.chat_message("assistant"):
        # Create request for the agent
        request = ResponsesAgentRequest(
            input=[{"role": msg["role"], "content": msg["content"]}
                   for msg in st.session_state.messages]
        )

        # Stream the response
        response_placeholder = st.empty()
        full_response = ""

        try:
            for event in agent.predict_stream(request):
                # Handle different event types from the Responses API
                if event.type == "response.output_text.delta":
                    # Accumulate text deltas
                    if hasattr(event, 'delta') and event.delta:
                        full_response += event.delta
                        response_placeholder.markdown(full_response + "▌")
                elif event.type == "response.output_item_done":
                    # Final complete response
                    if hasattr(event, 'output_item') and hasattr(event.output_item, 'content'):
                        for content_item in event.output_item.content:
                            if hasattr(content_item, 'text'):
                                full_response = content_item.text

            # Display final response without cursor
            response_placeholder.markdown(full_response)

            # Store the trace ID for feedback
            trace_id = mlflow.get_last_active_trace_id()
            if trace_id:
                st.session_state.trace_ids.append(trace_id)
                logger.info(f"Trace ID for this interaction: {trace_id}")

        except Exception as e:
            logger.error(f"Error querying endpoint: {e}")
            full_response = f"⚠️ Error: {str(e)}\n\nPlease check the endpoint configuration and try again."
            response_placeholder.markdown(full_response)

    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response})

# Sidebar with additional information
with st.sidebar:
    st.header("ℹ️ About")
    st.markdown(
        """
        This chatbot demonstrates:
        - **ResponsesAgent** pattern for production deployments
        - **MLflow tracing** for observability
        - **User feedback collection** for model improvement
        - **Streaming responses** for better UX

        Built with Databricks Agent Framework.
        """
    )

    st.header("📊 Session Info")
    st.write(f"**Messages:** {len(st.session_state.messages)}")
    st.write(f"**Traces:** {len(st.session_state.trace_ids)}")
    st.write(f"**Feedback:** {len(st.session_state.feedback_submitted)}")

    if st.button("🔄 Clear Chat"):
        st.session_state.messages = []
        st.session_state.trace_ids = []
        st.session_state.feedback_submitted = {}
        st.rerun()
