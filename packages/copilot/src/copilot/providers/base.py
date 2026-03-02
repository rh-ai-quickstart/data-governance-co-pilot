"""
Base provider interface for LLM + tool orchestration.

Defines the contract that all provider implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator


class LLMProvider(ABC):
    """
    Abstract base class for LLM provider implementations.

    Providers implement different strategies for orchestrating LLM inference
    with tool calling capabilities:
    - MCP-Direct: Backend manages agentic loop with direct vLLM + MCP client
    - Llama Stack: Delegates to Llama Stack Agents API for orchestration
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize provider (connect to services, discover tools).

        Raises:
            Exception: If initialization fails
        """
        pass

    @abstractmethod
    async def process_query_stream(
        self,
        user_query: str,
        conversation_id: str | None,
        enable_reasoning: bool,
        messages: list[dict] | None = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        Process user query and yield standardized SSE events.

        Must yield events with the following types:
        - query_start: Query processing begins
        - conversation_started/resumed: Conversation context info
        - iteration_start: New iteration begins (agentic loop)
        - llm_thinking: LLM's internal reasoning (if available)
        - llm_content_delta: Streaming LLM response text
        - tool_call: Tool execution initiated
        - tool_result: Tool execution completed
        - timing_summary: Performance breakdown
        - final_response: Complete answer
        - error: Error occurred

        Args:
            user_query: The user's question or request
            conversation_id: Optional conversation ID for context
            enable_reasoning: Whether to include reasoning in responses
            messages: Optional pre-populated message history

        Yields:
            dict: SSE event with type and relevant data
        """
        pass

    @abstractmethod
    def get_system_prompt(self, enable_reasoning: bool) -> str:
        """
        Build system prompt for the LLM.

        May differ by provider capabilities (e.g., Llama Stack may not support
        certain reasoning modes).

        Args:
            enable_reasoning: Whether to enable reasoning mode

        Returns:
            str: Complete system prompt
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """
        Cleanup provider resources (close connections, etc.).

        Called during shutdown to ensure graceful cleanup.
        """
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """
        Check if provider is healthy and ready to process queries.

        Returns:
            bool: True if provider is operational
        """
        pass

    @abstractmethod
    def requires_conversation_restart_on_policy_update(self) -> bool:
        """
        Check if updating governance policy requires restarting conversations.

        Some providers (like Llama Stack) bake policy into static agent instructions
        and require agent recreation. Others (like MCP-Direct) build prompts dynamically
        and can apply policy changes immediately.

        Returns:
            bool: True if conversations must be restarted when policy updates
        """
        pass

    @abstractmethod
    async def update_governance_policy(self, new_policy: str | None) -> None:
        """
        Update the governance policy.

        Provider-specific implementation may:
        - Simply update the policy field (MCP-Direct)
        - Recreate agents/sessions (Llama Stack)

        Args:
            new_policy: New policy text or None to remove policy
        """
        pass

    @abstractmethod
    def get_provider_mode(self) -> str:
        """
        Get the provider mode identifier.

        Returns:
            str: Provider mode (e.g., "mcp_direct", "llama_stack")
        """
        pass

    @abstractmethod
    def get_tool_count(self) -> int:
        """
        Get number of available tools.

        Returns:
            int: Number of tools available to the provider
        """
        pass
