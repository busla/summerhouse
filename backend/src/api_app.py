"""FastAPI application for Summerhouse Booking Agent.

Provides HTTP endpoints compatible with Vercel AI SDK v6:
- POST /invoke-stream - Streaming agent invocation (SSE)
- GET /ping - Health check
"""

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from src.agent import get_agent, reset_agent

app = FastAPI(
    title="Summerhouse Booking Agent",
    description="Agent-first vacation rental booking assistant",
    version="0.1.0",
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "Healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "agent": "summerhouse-booking",
    }


@app.post("/invoke-stream")
async def invoke_stream(request: Request) -> StreamingResponse:
    """Stream agent responses using AI SDK v6 UI Message Stream Protocol.

    Expects JSON body with:
        - messages: Array of model messages from the frontend

    Returns SSE stream with events:
        - {"type": "start", "messageId": "..."}
        - {"type": "text-start", "id": "..."}
        - {"type": "text-delta", "id": "...", "delta": "..."}
        - {"type": "text-end", "id": "..."}
        - {"type": "finish", "finishReason": "stop"}
    """
    body = await request.json()
    messages = body.get("messages", [])

    logger.info(f"Received {len(messages)} messages")
    for i, msg in enumerate(messages):
        logger.info(f"  Message {i}: role={msg.get('role')}, keys={list(msg.keys())}")

    # Extract the last user message as the prompt
    # AI SDK v6 uses "parts" array, older versions use "content"
    prompt = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            # AI SDK v6 format: parts array
            parts = msg.get("parts", [])
            if parts:
                for part in parts:
                    if isinstance(part, dict) and part.get("type") == "text":
                        prompt = part.get("text", "")
                        break
                if prompt:
                    break

            # Fallback: older format with content field
            content = msg.get("content", "")
            if isinstance(content, str):
                prompt = content
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        prompt = block.get("text", "")
                        break
            break

    logger.info(f"Extracted prompt: {prompt[:100] if prompt else '(empty)'!r}")

    if not prompt:
        return JSONResponse(
            {"error": "No user message found in messages array"},
            status_code=400,
        )

    return StreamingResponse(
        stream_agent_response(prompt),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )


async def stream_agent_response(prompt: str) -> AsyncGenerator[str, None]:
    """Stream agent response as SSE events in AI SDK v6 format."""
    message_id = f"msg_{uuid.uuid4().hex[:16]}"
    text_part_id = f"text_{uuid.uuid4().hex[:16]}"

    def sse_event(data: dict[str, Any]) -> str:
        return f"data: {json.dumps(data)}\n\n"

    # Send start event
    yield sse_event({"type": "start", "messageId": message_id})

    # Send text-start event
    yield sse_event({"type": "text-start", "id": text_part_id})

    agent = get_agent()

    try:
        # Stream from the agent
        async for event in agent.stream_async(prompt):
            # Handle different event types from Strands
            if isinstance(event, dict):
                event_type = event.get("type", "")

                # Text content events
                if event_type == "content_block_delta":
                    delta = event.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            yield sse_event({
                                "type": "text-delta",
                                "id": text_part_id,
                                "delta": text,
                            })

                # Also handle direct text in data field
                elif "data" in event and isinstance(event.get("data"), str):
                    yield sse_event({
                        "type": "text-delta",
                        "id": text_part_id,
                        "delta": event["data"],
                    })

            # Handle string events (raw text chunks)
            elif isinstance(event, str) and event:
                yield sse_event({
                    "type": "text-delta",
                    "id": text_part_id,
                    "delta": event,
                })

    except Exception as e:
        # Send error as text delta
        yield sse_event({
            "type": "text-delta",
            "id": text_part_id,
            "delta": f"\n\nError: {str(e)}",
        })

    # Send text-end event
    yield sse_event({"type": "text-end", "id": text_part_id})

    # Send finish event
    yield sse_event({"type": "finish", "finishReason": "stop"})


@app.post("/invoke")
async def invoke(request: Request) -> JSONResponse:
    """Non-streaming agent invocation (for simple requests)."""
    body = await request.json()
    prompt = body.get("prompt", "")

    if not prompt:
        return JSONResponse(
            {"error": "No prompt provided"},
            status_code=400,
        )

    agent = get_agent()

    try:
        result = agent(prompt)
        return JSONResponse({
            "message": str(result),
            "timestamp": datetime.now(UTC).isoformat(),
            "agent": "summerhouse-booking",
        })
    except Exception as e:
        return JSONResponse(
            {"error": f"Agent error: {str(e)}"},
            status_code=500,
        )


@app.post("/reset")
async def reset() -> JSONResponse:
    """Reset the agent conversation state."""
    reset_agent()
    return JSONResponse({
        "status": "ok",
        "message": "Agent conversation reset",
    })


def run_server(host: str = "0.0.0.0", port: int = 8080, reload: bool = True) -> None:
    """Run the FastAPI server.

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to listen on (default: 8080)
        reload: Enable hot reload for development (default: True)
    """
    import uvicorn

    if reload:
        # Use string reference for reload mode (uvicorn requirement)
        uvicorn.run(
            "src.api_app:app",
            host=host,
            port=port,
            reload=True,
            reload_dirs=["src"],
        )
    else:
        uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
