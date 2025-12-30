"""AgentCore Runtime entrypoint for Quesada Apartment Booking Agent.

This module provides the HTTP interface required by AWS Bedrock AgentCore Runtime:
- POST /invocations - Agent invocation endpoint (streaming via SSE)
- GET /ping - Health check endpoint

Implements Vercel AI SDK v6 UI Message Stream Protocol for frontend compatibility.

Session Management:
- Uses Strands S3SessionManager for conversation persistence
- Each session_id from the frontend maps to a unique conversation history
- Conversation history is restored when agent is created with session manager
- Uses synchronous agent() call with callback for proper session persistence
"""

import asyncio
import logging
import os
import queue
import sys
import uuid
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
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

# Thread pool for running sync agent calls
_executor = ThreadPoolExecutor(max_workers=10)


def _sse_event(data: dict[str, Any]) -> dict[str, Any]:
    """Wrap data in SSE-compatible format for AgentCore streaming.

    AgentCore's BedrockAgentCoreApp automatically converts yielded dicts
    to SSE format: `data: {json}\n\n`
    """
    return data


def _create_session_agent(session_id: str, callback_handler: Any = None) -> Any:
    """Create an agent with session management for conversation persistence.

    Args:
        session_id: Unique identifier for the conversation session.
                   Conversations with the same session_id share history.
        callback_handler: Optional callback for streaming events.

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
        return create_booking_agent(session_manager=session_manager, callback_handler=callback_handler)
    else:
        # Development/fallback: No session persistence
        # Each request creates a fresh agent without history
        logger.warning("SESSION_BUCKET not set - agent will not persist conversation history")
        return create_booking_agent(callback_handler=callback_handler)


def _run_agent_sync(agent: Any, prompt: str, event_queue: queue.Queue) -> None:
    """Run agent synchronously in a thread, pushing events to queue.

    This ensures the synchronous agent() call is used, which properly
    triggers session persistence hooks (unlike stream_async).
    """
    try:
        # The synchronous agent() call triggers session persistence automatically
        # The callback_handler receives streaming events
        agent(prompt)
        # Signal completion
        event_queue.put({"_done": True})
    except Exception as e:
        logger.error(f"Agent execution error: {e}")
        event_queue.put({"_error": str(e)})
        event_queue.put({"_done": True})


@app.entrypoint
async def invoke(payload: dict[str, Any]) -> AsyncGenerator[dict[str, Any]]:
    """Handle agent invocation requests with AI SDK v6 streaming.

    Creates a session-bound agent that maintains conversation history across
    multiple invocations with the same session_id.

    Uses synchronous agent() call with callback handler to ensure proper
    session persistence (stream_async doesn't trigger session save hooks).

    Args:
        payload: Request payload containing:
            - prompt: User message (required)
            - session_id: Session identifier for conversation continuity (required)

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
    message_id = f"msg_{uuid.uuid4().hex[:16]}"
    text_part_id = f"text_{uuid.uuid4().hex[:16]}"

    logger.info(f"Agent invocation: session_id={session_id}, prompt_length={len(prompt)}")

    if not prompt:
        # Emit error as AI SDK v6 stream
        yield _sse_event({"type": "start", "messageId": message_id})
        yield _sse_event({"type": "text-start", "id": text_part_id})
        yield _sse_event({
            "type": "text-delta",
            "id": text_part_id,
            "delta": "Error: No prompt provided. Please include a 'prompt' key in the request.",
        })
        yield _sse_event({"type": "text-end", "id": text_part_id})
        yield _sse_event({"type": "finish", "finishReason": "error"})
        return

    # Emit start events
    yield _sse_event({"type": "start", "messageId": message_id})
    yield _sse_event({"type": "text-start", "id": text_part_id})

    # Create queue for passing events from callback to async generator
    event_queue: queue.Queue = queue.Queue()

    # Callback handler that pushes text deltas to the queue
    def streaming_callback(**kwargs):
        """Callback handler that queues text deltas for streaming."""
        if "data" in kwargs and isinstance(kwargs["data"], str):
            event_queue.put({"text": kwargs["data"]})

    try:
        # Create a session-bound agent with callback handler
        agent = _create_session_agent(session_id, callback_handler=streaming_callback)

        # Run agent synchronously in thread pool (ensures session persistence)
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(_executor, _run_agent_sync, agent, prompt, event_queue)

        # Stream events from queue while agent runs
        while True:
            try:
                # Check for events with small timeout
                event = event_queue.get(timeout=0.1)

                if "_done" in event:
                    break
                elif "_error" in event:
                    yield _sse_event({
                        "type": "text-delta",
                        "id": text_part_id,
                        "delta": f"\n\nError: {event['_error']}",
                    })
                elif "text" in event and event["text"]:
                    yield _sse_event({
                        "type": "text-delta",
                        "id": text_part_id,
                        "delta": event["text"],
                    })

            except queue.Empty:
                # Check if executor is done
                if future.done():
                    # Drain remaining queue
                    while not event_queue.empty():
                        event = event_queue.get_nowait()
                        if "text" in event and event["text"]:
                            yield _sse_event({
                                "type": "text-delta",
                                "id": text_part_id,
                                "delta": event["text"],
                            })
                    break
                # Small yield to allow other coroutines
                await asyncio.sleep(0.01)

    except Exception as e:
        logger.error(f"Invoke error: {e}")
        yield _sse_event({
            "type": "text-delta",
            "id": text_part_id,
            "delta": f"\n\nError: {str(e)}",
        })

    # Emit end events
    yield _sse_event({"type": "text-end", "id": text_part_id})
    yield _sse_event({"type": "finish", "finishReason": "stop"})


if __name__ == "__main__":
    app.run()
