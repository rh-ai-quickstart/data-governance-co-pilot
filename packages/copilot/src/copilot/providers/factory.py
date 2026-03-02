"""
Provider factory for creating LLM provider instances.

Selects and instantiates the appropriate provider based on configuration.
"""

import logging
import os
from typing import Any

from .base import LLMProvider
from .mcp_direct import MCPDirectProvider
from .llama_stack import LlamaStackProvider

logger = logging.getLogger(__name__)


def create_provider(governance_policy: str | None = None) -> LLMProvider:
    """
    Create and return the appropriate LLM provider based on environment configuration.

    Environment Variables:
        COPILOT_PROVIDER_MODE: Provider mode (mcp_direct or llama_stack)

        MCP-Direct mode:
            LLM_BASE_URL: vLLM endpoint URL
            LLM_MODEL: Model identifier
            LLM_API_KEY: API key (optional)
            LLM_MAX_CONTEXT_LENGTH: Context window size
            LLM_TOOL_CALL_FORMAT: Tool calling format (auto/nemotron/openai)
            PG_AIRMAN_MCP_SERVICE_PORT: MCP server endpoint

        Llama Stack mode:
            LLAMA_STACK_BASE_URL: Llama Stack endpoint URL
            LLAMA_STACK_MODEL: Model identifier (vllm-inference/<name> format)
            PG_AIRMAN_MCP_SERVICE_URL: MCP server endpoint

    Args:
        governance_policy: Optional governance policy text to include in system prompt

    Returns:
        LLMProvider: Configured provider instance

    Raises:
        ValueError: If COPILOT_PROVIDER_MODE is invalid
    """
    provider_mode = os.getenv("COPILOT_PROVIDER_MODE", "mcp_direct").lower()

    logger.info(f"Creating provider with mode: {provider_mode}")

    if provider_mode == "mcp_direct":
        config = {
            "llm_base_url": os.getenv("LLM_BASE_URL", "http://nemotron-service:8000/v1"),
            "llm_model": os.getenv("LLM_MODEL", "nvidia/nemotron-nano-9b-v2"),
            "llm_api_key": os.getenv("LLM_API_KEY", "not-needed"),
            "llm_max_context_length": os.getenv("LLM_MAX_CONTEXT_LENGTH", "32768"),
            "llm_tool_call_format": os.getenv("LLM_TOOL_CALL_FORMAT", "auto"),
            "mcp_server_url": os.getenv("PG_AIRMAN_MCP_SERVICE_PORT", "http://pg-airman-mcp-service:8000")
        }

        logger.info("MCP-Direct provider configuration:")
        logger.info(f"  LLM Base URL: {config['llm_base_url']}")
        logger.info(f"  LLM Model: {config['llm_model']}")
        logger.info(f"  Tool Call Format: {config['llm_tool_call_format']}")
        logger.info(f"  MCP Server: {config['mcp_server_url']}")

        return MCPDirectProvider(config=config, governance_policy=governance_policy)

    elif provider_mode == "llama_stack":
        config = {
            "llama_stack_base_url": os.getenv("LLAMA_STACK_BASE_URL", "http://copilot-llama-stack:8000"),
            "llama_stack_model": os.getenv("LLAMA_STACK_MODEL", "vllm-inference/redhataillama-31-8b-instruct"),
            "mcp_server_url": os.getenv("PG_AIRMAN_MCP_SERVICE_URL", "http://pg-airman-mcp-service:8000")
        }

        logger.info("Llama Stack provider configuration:")
        logger.info(f"  Llama Stack Base URL: {config['llama_stack_base_url']}")
        logger.info(f"  Llama Stack Model: {config['llama_stack_model']}")
        logger.info(f"  MCP Server: {config['mcp_server_url']}")

        return LlamaStackProvider(config=config, governance_policy=governance_policy)

    else:
        raise ValueError(
            f"Invalid COPILOT_PROVIDER_MODE: {provider_mode}. "
            f"Must be 'mcp_direct' or 'llama_stack'"
        )
