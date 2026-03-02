"""
Provider abstraction layer for Data Governance Copilot.

Supports two deployment modes:
- MCP-Direct: Backend manages agentic loop with direct vLLM + MCP
- Llama Stack: Llama Stack manages agentic loop via Agents API
"""

from .base import LLMProvider
from .factory import create_provider

__all__ = ["LLMProvider", "create_provider"]
