import json
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


def render_agent_response(sections, streaming_text=""):
    """
    Build markdown for all response sections.

    Args:
        sections: List of (type, content) tuples
        streaming_text: Currently streaming text to append with cursor

    Returns:
        Tuple of (markdown_string, full_text_response)
    """
    markdown_parts = []
    full_text_parts = []

    for section_type, content in sections:
        if section_type == "text":
            markdown_parts.append(content)
            full_text_parts.append(content)

        elif section_type == "agent_name":
            markdown_parts.append(f"\n\n<details>\n<summary>🤖 Agent: {content}</summary>\n\nRouting to agent: {content}\n\n</details>\n")

        elif section_type == "tool_call":
            try:
                formatted_args = json.dumps(json.loads(content['args']), indent=2)
            except:
                formatted_args = content['args']
            markdown_parts.append(f"\n\n<details>\n<summary>🔧 Tool Call: {content['name']}</summary>\n\n```json\n{formatted_args}\n```\n\n</details>\n")

        elif section_type == "tool_output":
            # Skip displaying tool output if it's just a handoff message or contains large tables
            if content and not content.startswith("Handed off to:"):
                # Check if output looks like structured data (tables, large text)
                is_large_table = content.count('|') > 20 or len(content) > 1000

                if is_large_table:
                    # For large tables/data, just show a summary in the expander
                    lines = content.split('\n')[:3]
                    preview = '\n'.join(lines)
                    markdown_parts.append(f"\n\n<details>\n<summary>📤 Tool Output (large dataset - click to expand)</summary>\n\n```\n{preview}\n...\n[{len(content)} characters total]\n```\n\n</details>\n")
                else:
                    # Show smaller outputs normally
                    display_output = content if len(content) <= 500 else content[:500] + "\n\n... (truncated)"
                    markdown_parts.append(f"\n\n<details>\n<summary>📤 Tool Output</summary>\n\n```\n{display_output}\n```\n\n</details>\n")

    # Show currently streaming text with cursor
    if streaming_text:
        markdown_parts.append("\n\n" + streaming_text + "▌")
        full_text_parts.append(streaming_text)

    return "".join(markdown_parts), "\n\n".join(full_text_parts)


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
        if message["role"] == "assistant":
            # Calculate which trace this message corresponds to
            assistant_idx = sum(1 for m in st.session_state.messages[:idx+1] if m["role"] == "assistant") - 1

            if assistant_idx < len(st.session_state.trace_ids):
                trace_id = st.session_state.trace_ids[assistant_idx]

                # Only show buttons if feedback hasn't been submitted for this message
                if trace_id not in st.session_state.feedback_submitted:
                    st.markdown("---")
                    col1, col2, col3 = st.columns([1, 1, 10])
                    with col1:
                        if st.button("👍", key=f"thumbs_up_{idx}"):
                            logger.info(f"User clicked thumbs up for message {idx}, trace_id: {trace_id}")
                            success = log_user_feedback(trace_id, True, user_id=user_info["user_id"])
                            if success:
                                st.session_state.feedback_submitted[trace_id] = "positive"
                                logger.info("Feedback logged successfully")
                            else:
                                st.error("Failed to submit feedback. Please check the logs.")
                            st.rerun()
                    with col2:
                        if st.button("👎", key=f"thumbs_down_{idx}"):
                            logger.info(f"User clicked thumbs down for message {idx}, trace_id: {trace_id}")
                            success = log_user_feedback(trace_id, False, user_id=user_info["user_id"])
                            if success:
                                st.session_state.feedback_submitted[trace_id] = "negative"
                                logger.info("Feedback logged successfully")
                            else:
                                st.error("Failed to submit feedback. Please check the logs.")
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

        # Stream the response with full agent reasoning display
        try:
            logger.info("Starting streaming response...")
            event_count = 0

            # Track all response sections
            sections = []  # List of tuples: (type, content)
            current_text = ""
            current_item_id = None
            streamed_item_ids = set()  # Track which items we've streamed

            # Single placeholder for updating display
            response_placeholder = st.empty()

            for event in agent.predict_stream(request):
                event_count += 1
                logger.info(f"Event {event_count}: type={event.type}, event class={type(event).__name__}")

                # Handle different event types from the Responses API
                if event.type == "response.output_text.delta":
                    # Accumulate text deltas for the current streaming message
                    if hasattr(event, 'delta') and event.delta:
                        if hasattr(event, 'item_id') and event.item_id != current_item_id:
                            # New text stream starting
                            if current_text:
                                # Save previous text section
                                sections.append(("text", current_text))
                                streamed_item_ids.add(current_item_id)
                            current_text = event.delta
                            current_item_id = event.item_id
                        else:
                            current_text += event.delta

                        # Update display (only during streaming text)
                        markdown, _ = render_agent_response(sections, current_text)
                        response_placeholder.markdown(markdown, unsafe_allow_html=True)

                elif event.type == "response.output_item.done":
                    # Save any accumulated text first
                    if current_text:
                        sections.append(("text", current_text))
                        streamed_item_ids.add(current_item_id)
                        current_text = ""
                        current_item_id = None

                    if hasattr(event, 'item'):
                        item = event.item
                        item_id = getattr(item, 'id', None)
                        logger.info(f"Item type: {getattr(item, 'type', 'unknown')}, id: {item_id}")

                        # Handle different item types
                        if hasattr(item, 'type'):
                            if item.type == 'function_call':
                                # Show tool call
                                tool_name = getattr(item, 'name', 'unknown')
                                tool_args = getattr(item, 'arguments', '{}')
                                sections.append(("tool_call", {"name": tool_name, "args": tool_args}))
                                # Update display
                                markdown, _ = render_agent_response(sections)
                                response_placeholder.markdown(markdown, unsafe_allow_html=True)

                            elif item.type == 'function_call_output':
                                # Show tool output
                                output = getattr(item, 'output', '')
                                sections.append(("tool_output", output))
                                # Update display
                                markdown, _ = render_agent_response(sections)
                                response_placeholder.markdown(markdown, unsafe_allow_html=True)

                            elif item.type == 'message':
                                # Only process message items that we haven't already streamed
                                if item_id not in streamed_item_ids:
                                    # Extract any complete text from message items
                                    if hasattr(item, 'content'):
                                        for content_item in item.content:
                                            if hasattr(content_item, 'type') and content_item.type == 'output_text':
                                                if hasattr(content_item, 'text'):
                                                    # Check if this is agent name metadata (contains <name>)
                                                    text = content_item.text
                                                    if text.startswith('<name>') and text.endswith('</name>'):
                                                        agent_name = text[6:-7]  # Extract name
                                                        sections.append(("agent_name", agent_name))
                                                        # Update display
                                                        markdown, _ = render_agent_response(sections)
                                                        response_placeholder.markdown(markdown, unsafe_allow_html=True)
                                                    elif text != "EMPTY":
                                                        # Add non-streamed message text
                                                        sections.append(("text", text))
                                                        # Update display
                                                        markdown, _ = render_agent_response(sections)
                                                        response_placeholder.markdown(markdown, unsafe_allow_html=True)

            # Final render without cursor
            markdown, full_response = render_agent_response(sections)
            response_placeholder.markdown(markdown, unsafe_allow_html=True)
            logger.info(f"Stream complete. Total events: {event_count}, Sections: {len(sections)}")

            # Store the trace ID for feedback (from manual tracing)
            try:
                logger.info("Retrieving trace ID from agent...")
                trace_id = agent.get_last_trace_id()
                if trace_id:
                    logger.info(f"Trace ID retrieved: {trace_id}")
                    st.session_state.trace_ids.append(trace_id)
                    logger.info(f"Trace ID stored successfully. Total traces: {len(st.session_state.trace_ids)}")
                else:
                    logger.warning("No trace ID available from agent")
            except Exception as e:
                logger.error(f"Error retrieving or storing trace ID: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error querying endpoint: {e}", exc_info=True)
            full_response = f"⚠️ Error: {str(e)}\n\nPlease check the endpoint configuration and try again."
            response_placeholder.markdown(full_response)

    # Add assistant response to chat history
    try:
        logger.info(f"Storing assistant response in session state (length: {len(full_response)})")
        st.session_state.messages.append({"role": "assistant", "content": full_response})
        logger.info("Successfully stored assistant response")
        # Trigger rerun to show feedback buttons
        st.rerun()
    except Exception as e:
        logger.error(f"Error storing assistant response in session state: {e}", exc_info=True)
        # Try to store a simplified version
        st.session_state.messages.append({"role": "assistant", "content": str(full_response)})
        st.rerun()

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
