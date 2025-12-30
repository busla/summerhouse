"""AgentCore Runtime entrypoint for Quesada Apartment Booking Agent.

This module provides the HTTP interface required by AWS Bedrock AgentCore Runtime:
- POST /invocations - Agent invocation endpoint (streaming via SSE)
- GET /ping - Health check endpoint

Implements Vercel AI SDK v6 UI Message Stream Protocol for frontend compatibility.

Session Management:
- Uses Strands S3SessionManager for conversation persistence
- Each session_id from the frontend maps to a unique conversation history
- Uses stream_async for native async streaming (follows AgentCore samples pattern)
"""

import logging
import os
import sys
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands.session.s3_session_manager import S3SessionManager

from src.agent import create_booking_agent

# Configure logging - MUST happen before any logger.info() calls
# This routes all Python logging to stdout/stderr for CloudWatch capture
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
    force=True,  # Override any existing configuration
)

logger = logging.getLogger(__name__)
logger.info("[AGENT_APP] Logging configured successfully")

# Initialize AgentCore app
app = BedrockAgentCoreApp()

# Session configuration from environment
SESSION_BUCKET = os.environ.get("SESSION_BUCKET", "")
SESSION_PREFIX = os.environ.get("SESSION_PREFIX", "agent-sessions/")


def _create_session_agent(session_id: str) -> Any:
    """Create an agent with session management for conversation persistence.

    Args:
        session_id: Unique identifier for the conversation session.
                   Conversations with the same session_id share history.

    Returns:
        Agent instance configured with S3 session manager (if SESSION_BUCKET is set)
        or a basic agent without session persistence (for local development).
    """
    if SESSION_BUCKET:
        # Production: Use S3 for session persistence
        logger.info(f"Creating agent with S3 session: bucket={SESSION_BUCKET}, session={session_id}")
        session_manager = S3SessionManager(
            session_id=session_id,
            bucket=SESSION_BUCKET,
            prefix=SESSION_PREFIX,
        )
        return create_booking_agent(session_manager=session_manager)
    else:
        # Development/fallback: No session persistence
        logger.warning("SESSION_BUCKET not set - agent will not persist conversation history")
        return create_booking_agent()


@app.entrypoint
async def invoke(payload: dict[str, Any]) -> AsyncGenerator[dict[str, Any]]:
    """Handle agent invocation requests with AI SDK v6 streaming.

    Uses stream_async for native async streaming (follows AgentCore samples pattern).

    Args:
        payload: Request payload containing:
            - prompt: User message (required)
            - session_id: Session identifier for conversation continuity (required)
            - auth_token: Optional JWT token for authenticated requests

    Yields:
        AI SDK v6 UI Message Stream Protocol events:
        - {"type": "start", "messageId": "..."}
        - {"type": "text-start", "id": "..."}
        - {"type": "text-delta", "id": "...", "delta": "..."}
        - {"type": "text-end", "id": "..."}
        - {"type": "finish", "finishReason": "stop"}
    """
    prompt = payload.get("prompt", "")
    session_id = payload.get("session_id", str(uuid.uuid4()))
    auth_token = payload.get("auth_token")
    message_id = f"msg_{uuid.uuid4().hex[:16]}"
    text_part_id = f"text_{uuid.uuid4().hex[:16]}"

    request_type = "authenticated" if auth_token else "anonymous"
    logger.info(f"Agent invocation: session_id={session_id}, type={request_type}, prompt_length={len(prompt)}")

    if not prompt:
        # Emit error as AI SDK v6 stream
        yield {"type": "start", "messageId": message_id}
        yield {"type": "text-start", "id": text_part_id}
        yield {
            "type": "text-delta",
            "id": text_part_id,
            "delta": "Error: No prompt provided. Please include a 'prompt' key in the request.",
        }
        yield {"type": "text-end", "id": text_part_id}
        yield {"type": "finish", "finishReason": "error"}
        return

    # Emit start events
    yield {"type": "start", "messageId": message_id}
    yield {"type": "text-start", "id": text_part_id}

    try:
        # Create a session-bound agent
        agent = _create_session_agent(session_id)

        # Set auth_token in agent state for tools to access via ToolContext
        if auth_token:
            agent.state.set("auth_token", auth_token)

        # Use stream_async for native async streaming (follows AgentCore samples pattern)
        async for event in agent.stream_async(prompt):
            # Handle text chunks from model output
            if "data" in event and event["data"]:
                yield {
                    "type": "text-delta",
                    "id": text_part_id,
                    "delta": event["data"],
                }

    except Exception as e:
        logger.error(f"Invoke error: {e}")
        yield {
            "type": "text-delta",
            "id": text_part_id,
            "delta": f"\n\nError: {str(e)}",
        }

    # Emit end events
    yield {"type": "text-end", "id": text_part_id}
    yield {"type": "finish", "finishReason": "stop"}


if __name__ == "__main__":
    app.run()
