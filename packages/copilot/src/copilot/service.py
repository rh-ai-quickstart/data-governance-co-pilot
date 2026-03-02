"""
Data Governance Copilot Service

FastAPI backend that orchestrates interactions between:
- LLM providers (MCP-Direct or Llama Stack)
- pg-airman-mcp server (PostgreSQL analysis tools)

The service now uses a provider abstraction layer to support multiple deployment modes.
"""
import json
import logging
import os
import traceback

# Set up logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .providers import create_provider, LLMProvider


class QueryRequest(BaseModel):
    """User query request model"""
    query: str
    conversation_id: str | None = None
    enable_reasoning: bool = True  # Whether to include reasoning in LLM responses


class PolicyUploadRequest(BaseModel):
    """Request model for uploading governance policy"""
    policy_text: str
    conversation_id: str | None = None  # Optional: conversation to delete if restart required


class PolicyResponse(BaseModel):
    """Response model for policy operations"""
    status: str
    policy_length: int | None = None
    message: str | None = None
    provider_mode: str | None = None  # Provider mode (mcp_direct or llama_stack)
    requires_restart: bool | None = None  # Whether conversations need to be restarted


class PolicyStatusResponse(BaseModel):
    """Response model for policy status check"""
    has_policy: bool
    policy_length: int | None = None
    policy_preview: str | None = None


class DataGovernanceCopilot:
    """
    Thin orchestrator for LLM provider interactions.

    This class delegates actual LLM + tool orchestration to provider implementations.
    It manages:
    1. Provider lifecycle (creation, initialization, cleanup)
    2. Conversation state management
    3. Policy storage and injection into provider context
    """

    def __init__(self, governance_policy: str | None = None):
        """
        Initialize copilot with provider factory.

        Args:
            governance_policy: Optional governance policy to pass to provider
        """
        self.governance_policy = governance_policy
        self.provider: LLMProvider | None = None

        # Create provider based on environment configuration
        logger.info("Creating provider via factory...")
        self.provider = create_provider(governance_policy=governance_policy)

    async def initialize(self):
        """Initialize the provider"""
        logger.info("Initializing provider...")
        await self.provider.initialize()
        logger.info("Provider initialization complete!")

    async def process_query_stream(self, user_query: str, conversation_id: str | None = None, enable_reasoning: bool = True, messages: list[dict] | None = None):
        """
        Process user query through the provider.

        Args:
            user_query: The user's question or request
            conversation_id: Optional conversation ID for maintaining context
            enable_reasoning: Whether to include reasoning in responses
            messages: Optional pre-populated message history

        Yields:
            SSE events from the provider
        """
        async for event in self.provider.process_query_stream(
            user_query=user_query,
            conversation_id=conversation_id,
            enable_reasoning=enable_reasoning,
            messages=messages
        ):
            yield event

    async def cleanup(self):
        """Cleanup provider resources"""
        if self.provider:
            await self.provider.cleanup()

    def is_healthy(self) -> bool:
        """Check if provider is healthy"""
        if not self.provider:
            return False
        return self.provider.is_healthy()

    def get_tool_count(self) -> int:
        """Get number of available tools"""
        if not self.provider:
            return 0
        return self.provider.get_tool_count()


# Initialize FastAPI app
app = FastAPI(
    title="Data Governance Copilot API",
    description="Backend service for data governance copilot with LLM and MCP integration",
    version="0.1.0"
)

# Add CORS middleware for Svelte frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global copilot instance
copilot: DataGovernanceCopilot | None = None

# Conversation store: conversation_id -> list of messages
# In production, this should be replaced with a persistent store (Redis, DB, etc.)
conversation_store: dict[str, list[dict[str, str]]] = {}

# Policy store: single active policy text (in-memory only)
# Policy is included in system prompt for new conversations
# Only one policy can be active at a time - uploading a new one replaces the old one
governance_policy: str | None = None


@app.on_event("startup")
async def startup_event():
    """Initialize copilot on startup"""
    global copilot
    copilot = DataGovernanceCopilot(governance_policy=governance_policy)
    await copilot.initialize()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "provider_healthy": copilot.is_healthy() if copilot else False,
        "tools_available": copilot.get_tool_count() if copilot else 0,
        "provider_mode": os.getenv("COPILOT_PROVIDER_MODE", "mcp_direct")
    }


@app.get("/provider/info")
async def get_provider_info():
    """
    Get provider information including whether policy updates require conversation restart.

    This allows the UI to determine whether to show a confirmation dialog before
    uploading a governance policy.
    """
    if not copilot or not copilot.provider:
        raise HTTPException(status_code=500, detail="Copilot provider not initialized")

    return {
        "provider_mode": copilot.provider.get_provider_mode(),
        "requires_restart_on_policy_update": copilot.provider.requires_conversation_restart_on_policy_update(),
        "tool_count": copilot.provider.get_tool_count()
    }


@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    """
    Process user query with Server-Sent Events (SSE) for real-time progress updates.

    Streams events including:
    - iteration_start: When each iteration begins
    - llm_thinking: LLM's reasoning process
    - tool_call: When tools are executed
    - tool_result: Tool execution complete (timing only, no data for governance)
    - final_response: The complete answer
    - timing_summary: Performance breakdown
    - error: If something goes wrong
    """
    if not copilot:
        raise HTTPException(status_code=503, detail="Copilot not initialized")

    async def event_generator():
        """Generate SSE formatted events"""
        try:
            # Get or create conversation history
            messages = None
            if request.conversation_id and request.conversation_id in conversation_store:
                messages = conversation_store[request.conversation_id].copy()
                # Update system prompt to match current reasoning setting and policy
                if messages and messages[0]["role"] == "system":
                    messages[0]["content"] = copilot.provider.get_system_prompt(enable_reasoning=request.enable_reasoning)

            # Stream events from provider
            async for event in copilot.process_query_stream(
                request.query,
                request.conversation_id,
                request.enable_reasoning,
                messages
            ):
                # Store conversation messages on final response
                if event.get("type") == "final_response" and request.conversation_id:
                    # Save updated messages to conversation store
                    if "messages" in event:
                        conversation_store[request.conversation_id] = event["messages"]
                        # Remove messages from event before sending to client (too large)
                        event = {k: v for k, v in event.items() if k != "messages"}

                # Format as SSE: data: {json}\n\n
                event_type = event.get("type", "unknown")
                logger.info(f"[SSE] Sending event: {event_type}")
                if event_type == "timing_summary":
                    logger.info(f"[SSE] timing_summary content: {event}")
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            error_event = {
                "type": "error",
                "message": str(e),
                "traceback": traceback.format_exc()
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.get("/tools")
async def list_tools():
    """List available tools"""
    if not copilot:
        raise HTTPException(status_code=503, detail="Copilot not initialized")

    return {
        "tools": copilot.provider.mcp_tools if hasattr(copilot.provider, 'mcp_tools') else [],
        "count": copilot.get_tool_count()
    }


@app.get("/conversations")
async def list_conversations():
    """List active conversations (for debugging)"""
    return {
        "conversations": [
            {
                "id": conv_id,
                "message_count": len(messages),
                "last_message": messages[-1]["content"][:100] if messages else None
            }
            for conv_id, messages in conversation_store.items()
        ],
        "total": len(conversation_store)
    }


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation and its associated session"""
    if conversation_id in conversation_store:
        del conversation_store[conversation_id]
        # Also delete the Llama Stack session if using Llama Stack provider
        if copilot and hasattr(copilot.provider, 'delete_conversation_session'):
            await copilot.provider.delete_conversation_session(conversation_id)
        return {"status": "deleted", "conversation_id": conversation_id}
    else:
        raise HTTPException(status_code=404, detail="Conversation not found")


# ============================================================================
# Policy Management Endpoints
# ============================================================================

@app.post("/policy/upload", response_model=PolicyResponse)
async def upload_policy(request: PolicyUploadRequest):
    """
    Upload or replace data governance policy.
    Only one policy can be active at a time - uploading replaces the existing policy.

    For MCP-Direct mode: Policy applies immediately to new messages.
    For Llama Stack mode: Agent is recreated and all sessions invalidated.

    Args:
        request: Contains policy_text and optional conversation_id to delete
    """
    global governance_policy, copilot

    if not request.policy_text or not request.policy_text.strip():
        raise HTTPException(status_code=400, detail="Policy text cannot be empty")

    if not copilot or not copilot.provider:
        raise HTTPException(status_code=500, detail="Copilot provider not initialized")

    governance_policy = request.policy_text.strip()
    logger.info(f"Policy uploaded successfully - {len(governance_policy)} characters")
    logger.info(f"Policy preview: {governance_policy[:200]}...")

    # Update the provider's governance policy
    try:
        await copilot.provider.update_governance_policy(governance_policy)
    except Exception as e:
        logger.error(f"Failed to update provider policy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update provider policy: {str(e)}")

    # Get provider information
    provider_mode = copilot.provider.get_provider_mode()
    requires_restart = copilot.provider.requires_conversation_restart_on_policy_update()

    # If conversation restart is required and conversation_id provided, delete it
    if requires_restart and request.conversation_id:
        logger.info(f"Deleting conversation {request.conversation_id} after policy update")
        if request.conversation_id in conversation_store:
            del conversation_store[request.conversation_id]
            # Also delete Llama Stack session if applicable
            if hasattr(copilot.provider, 'delete_conversation_session'):
                await copilot.provider.delete_conversation_session(request.conversation_id)
            logger.info(f"Conversation {request.conversation_id} deleted")

    # Build response message
    if requires_restart:
        message = f"Policy updated successfully. Agent recreated - all conversations must be restarted."
    else:
        message = f"Policy updated successfully. Will apply to new messages immediately."

    return PolicyResponse(
        status="uploaded",
        policy_length=len(governance_policy),
        message=message,
        provider_mode=provider_mode,
        requires_restart=requires_restart
    )


@app.delete("/policy", response_model=PolicyResponse)
async def delete_policy():
    """
    Remove the active data governance policy.

    For MCP-Direct mode: Policy removal applies immediately to new messages.
    For Llama Stack mode: Agent is recreated without policy and all sessions invalidated.
    """
    global governance_policy, copilot

    if governance_policy is None:
        raise HTTPException(status_code=404, detail="No policy currently active")

    if not copilot or not copilot.provider:
        raise HTTPException(status_code=500, detail="Copilot provider not initialized")

    logger.info("Policy deleted - new conversations will use default system prompt")
    governance_policy = None

    # Update the provider to remove policy
    try:
        await copilot.provider.update_governance_policy(None)
    except Exception as e:
        logger.error(f"Failed to update provider policy: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update provider policy: {str(e)}")

    # Get provider information
    provider_mode = copilot.provider.get_provider_mode()
    requires_restart = copilot.provider.requires_conversation_restart_on_policy_update()

    # Build response message
    if requires_restart:
        message = "Policy deleted successfully. Agent recreated - all conversations must be restarted."
    else:
        message = "Policy deleted successfully. Will apply to new messages immediately."

    return PolicyResponse(
        status="deleted",
        policy_length=None,
        message=message,
        provider_mode=provider_mode,
        requires_restart=requires_restart
    )


@app.get("/policy/status", response_model=PolicyStatusResponse)
async def get_policy_status():
    """
    Get status of current data governance policy.
    Returns whether a policy is active and a preview of its content.
    """
    global governance_policy

    if governance_policy is None:
        return PolicyStatusResponse(
            has_policy=False,
            policy_length=None,
            policy_preview=None
        )

    return PolicyStatusResponse(
        has_policy=True,
        policy_length=len(governance_policy),
        policy_preview=governance_policy[:200] + ("..." if len(governance_policy) > 200 else "")
    )
