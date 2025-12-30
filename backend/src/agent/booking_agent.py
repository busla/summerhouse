"""Quesada Apartment Booking Agent using Strands framework."""

import os
from pathlib import Path
from typing import Any

from strands import Agent
from strands.agent.conversation_manager import SlidingWindowConversationManager
from strands.models import BedrockModel

from src.tools import ALL_TOOLS

# Default to Opus for production, can be overridden via env var for testing
DEFAULT_MODEL_ID = "eu.anthropic.claude-opus-4-5-20251101-v1:0"


def _load_system_prompt() -> str:
    """Load system prompt from markdown file."""
    prompt_path = Path(__file__).parent / "prompts" / "system_prompt.md"
    return prompt_path.read_text()


def create_booking_agent(
    tools: list[Any] | None = None,
    session_manager: Any | None = None,
    callback_handler: Any | None = None,
) -> Agent:
    """Create and configure the Quesada Apartment booking agent.

    Args:
        tools: List of tools to provide to the agent. If None, uses ALL_TOOLS.
        session_manager: Optional session manager for conversation persistence.
                        When provided, the agent will restore and save conversation
                        history using the session manager's storage backend (e.g., S3).
        callback_handler: Optional callback for streaming events. Used with sync
                         agent() call to stream responses while ensuring session
                         persistence.

    Returns:
        Configured Agent instance with optional session persistence.
    """
    # Configure conversation manager for context window management
    # This handles trimming when messages exceed the model's context window
    conversation_manager = SlidingWindowConversationManager(
        window_size=40,
        should_truncate_results=True,
    )

    # Configure Bedrock model with EU inference profile
    # Model ID can be overridden via BEDROCK_MODEL_ID env var (e.g., for tests)
    model_id = os.environ.get("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    bedrock_model = BedrockModel(
        model_id=model_id,
        region_name="eu-west-1",
    )

    # Use provided tools or default to ALL_TOOLS
    agent_tools = tools if tools is not None else ALL_TOOLS

    # Build agent with optional session manager for persistence
    # callback_handler enables streaming via sync agent() call
    agent = Agent(
        model=bedrock_model,
        tools=agent_tools,
        system_prompt=_load_system_prompt(),
        conversation_manager=conversation_manager,
        session_manager=session_manager,  # Enables conversation history persistence
        callback_handler=callback_handler,  # Enables streaming with sync call
    )

    return agent


# Singleton agent instance for the application
_agent_instance: Agent | None = None


def get_agent(tools: list[Any] | None = None) -> Agent:
    """Get or create the singleton booking agent.

    Args:
        tools: Tools to use if creating new agent. If None, uses ALL_TOOLS.

    Returns:
        The booking agent instance
    """
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = create_booking_agent(tools)
    return _agent_instance


def reset_agent() -> None:
    """Reset the agent instance (useful for testing)."""
    global _agent_instance
    _agent_instance = None
