"""
Tool Validation for MCP Server Tools

This module provides security validation for MCP tool calls:
1. Hard-coded allowlist of approved tools (fail-closed)
2. Pydantic schema validation for tool arguments
3. Logging for security events (unknown tools, malformed arguments)

Security Rationale:
- Defense against prompt injection attacks that coerce LLM to call unauthorized tools
- Type safety validation prevents malformed arguments from reaching MCP server
- Fail-closed approach: reject unknown tools even if MCP server advertises them
"""

import logging
from typing import Any, Dict, Optional, Set
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


# ============================================================================
# Tool Argument Schemas (Pydantic Models)
# ============================================================================

class ExecuteSqlArgs(BaseModel):
    """Arguments for execute_sql tool"""
    query: str = Field(..., description="SQL query to execute")
    restricted: bool = Field(default=True, description="Run in restricted mode (SELECT only)")


class ListSchemasArgs(BaseModel):
    """Arguments for list_schemas tool (no arguments required)"""
    pass


class ListObjectsArgs(BaseModel):
    """Arguments for list_objects tool"""
    schema_name: str = Field(..., description="Schema name to list objects from")
    object_type: Optional[str] = Field(None, description="Filter by object type: table, view, index, etc.")


class GetObjectDetailsArgs(BaseModel):
    """Arguments for get_object_details tool"""
    schema_name: str = Field(..., description="Schema name")
    object_name: str = Field(..., description="Object name (table, view, etc.)")
    object_type: str = Field(..., description="Object type: table, view, column, index, etc.")


class ExplainQueryArgs(BaseModel):
    """Arguments for explain_query tool"""
    query: str = Field(..., description="SQL query to explain")
    analyze: bool = Field(default=False, description="Run EXPLAIN ANALYZE (actually executes query)")


class AddCommentToObjectArgs(BaseModel):
    """Arguments for add_comment_to_object tool"""
    schema_name: str = Field(..., description="Schema name")
    object_type: str = Field(..., description="Object type: table, view, column")
    object_name: str = Field(..., description="Object name")
    comment: str = Field(..., description="Comment text to add")
    column_name: Optional[str] = Field(None, description="Column name (required if object_type=column)")


class AnalyzeWorkloadIndexesArgs(BaseModel):
    """Arguments for analyze_workload_indexes tool"""
    schema_name: Optional[str] = Field(None, description="Filter by schema name")
    table_name: Optional[str] = Field(None, description="Filter by table name")


class GetTopQueriesArgs(BaseModel):
    """Arguments for get_top_queries tool"""
    limit: int = Field(default=10, ge=1, le=100, description="Number of queries to return")
    order_by: str = Field(default="total_exec_time", description="Sort by: total_exec_time, calls, mean_exec_time")


# ============================================================================
# Tool Schema Registry
# ============================================================================

TOOL_SCHEMAS: Dict[str, type[BaseModel]] = {
    "execute_sql": ExecuteSqlArgs,
    "list_schemas": ListSchemasArgs,
    "list_objects": ListObjectsArgs,
    "get_object_details": GetObjectDetailsArgs,
    "explain_query": ExplainQueryArgs,
    "add_comment_to_object": AddCommentToObjectArgs,
    "analyze_workload_indexes": AnalyzeWorkloadIndexesArgs,
    "get_top_queries": GetTopQueriesArgs,
}

# Hard-coded allowlist of approved tools (fail-closed)
ALLOWED_TOOLS: Set[str] = set(TOOL_SCHEMAS.keys())


# ============================================================================
# Validation Functions
# ============================================================================

class ToolValidationError(Exception):
    """Raised when tool validation fails"""
    pass


def validate_tool_name(tool_name: str) -> None:
    """
    Validate that tool name is in the approved allowlist.

    Args:
        tool_name: Name of the tool to validate

    Raises:
        ToolValidationError: If tool is not in allowlist
    """
    if tool_name not in ALLOWED_TOOLS:
        logger.error(
            f"SECURITY: LLM attempted to call unauthorized tool: {tool_name}. "
            f"Allowed tools: {sorted(ALLOWED_TOOLS)}"
        )
        raise ToolValidationError(
            f"Tool '{tool_name}' is not in the approved allowlist. "
            f"This may indicate a prompt injection attack."
        )

    logger.debug(f"Tool name validation passed: {tool_name}")


def validate_tool_arguments(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate tool arguments against Pydantic schema.

    Args:
        tool_name: Name of the tool
        arguments: Arguments dict from LLM

    Returns:
        Validated and coerced arguments dict

    Raises:
        ToolValidationError: If arguments don't match schema
    """
    if tool_name not in TOOL_SCHEMAS:
        raise ToolValidationError(f"No schema found for tool: {tool_name}")

    schema = TOOL_SCHEMAS[tool_name]

    try:
        # Validate and coerce arguments using Pydantic
        validated = schema(**arguments)
        # Return as dict for MCP call
        validated_dict = validated.model_dump(exclude_none=True)

        logger.debug(
            f"Tool argument validation passed: {tool_name} with {len(validated_dict)} arguments"
        )

        return validated_dict

    except ValidationError as e:
        logger.error(
            f"SECURITY: Tool argument validation failed for {tool_name}. "
            f"Errors: {e.errors()}"
        )
        raise ToolValidationError(
            f"Invalid arguments for tool '{tool_name}': {e.errors()}"
        )


def validate_tool_call(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Complete validation of tool call (name + arguments).

    Args:
        tool_name: Name of the tool to call
        arguments: Arguments dict from LLM

    Returns:
        Validated arguments dict

    Raises:
        ToolValidationError: If validation fails
    """
    # Step 1: Validate tool name is in allowlist
    validate_tool_name(tool_name)

    # Step 2: Validate arguments against schema
    validated_args = validate_tool_arguments(tool_name, arguments)

    return validated_args


def check_mcp_server_tools(advertised_tools: list[str]) -> None:
    """
    Check if MCP server advertises tools that differ from our allowlist.

    Logs warnings for:
    - Tools advertised by server but not in our allowlist (potential security risk)
    - Tools in our allowlist but not advertised by server (configuration issue)

    Args:
        advertised_tools: List of tool names from MCP server's tools/list
    """
    advertised_set = set(advertised_tools)

    # Tools advertised but not in allowlist (potential attack or server misconfiguration)
    unknown_tools = advertised_set - ALLOWED_TOOLS
    if unknown_tools:
        logger.warning(
            f"SECURITY: MCP server advertises tools not in allowlist: {sorted(unknown_tools)}. "
            f"These tools will be rejected if LLM attempts to call them."
        )

    # Tools in allowlist but not advertised (configuration issue)
    missing_tools = ALLOWED_TOOLS - advertised_set
    if missing_tools:
        logger.warning(
            f"Configuration warning: Tools in allowlist but not advertised by MCP server: {sorted(missing_tools)}. "
            f"These tools cannot be called until server configuration is updated."
        )

    # Log success case
    if not unknown_tools and not missing_tools:
        logger.info(
            f"MCP server tool list matches allowlist ({len(ALLOWED_TOOLS)} tools): {sorted(ALLOWED_TOOLS)}"
        )
