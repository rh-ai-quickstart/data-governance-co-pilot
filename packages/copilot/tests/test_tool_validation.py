"""
Unit tests for tool validation module.

Tests security validation for MCP tool calls:
- Tool name allowlist enforcement
- Argument schema validation
- Error handling for malformed inputs
"""

import pytest
from copilot.providers.tool_validation import (
    validate_tool_call,
    validate_tool_name,
    validate_tool_arguments,
    check_mcp_server_tools,
    ToolValidationError,
    ALLOWED_TOOLS
)


class TestToolNameValidation:
    """Tests for tool name allowlist validation"""

    def test_valid_tool_name(self):
        """Valid tool names should pass validation"""
        validate_tool_name("execute_sql")
        validate_tool_name("list_schemas")
        validate_tool_name("get_top_queries")
        # No exception raised = pass

    def test_invalid_tool_name(self):
        """Unknown tool names should be rejected"""
        with pytest.raises(ToolValidationError, match="not in the approved allowlist"):
            validate_tool_name("_internal_dangerous_function")

        with pytest.raises(ToolValidationError, match="not in the approved allowlist"):
            validate_tool_name("drop_database")


class TestArgumentValidation:
    """Tests for tool argument schema validation"""

    def test_execute_sql_valid_args(self):
        """execute_sql with valid arguments should pass"""
        args = {"sql": "SELECT * FROM users"}
        result = validate_tool_arguments("execute_sql", args)
        assert result["sql"] == "SELECT * FROM users"

    def test_execute_sql_default_values(self):
        """execute_sql should apply default values"""
        args = {}
        result = validate_tool_arguments("execute_sql", args)
        assert result["sql"] == "all"  # Default value

    def test_list_schemas_with_required_noop(self):
        """list_schemas requires noop argument"""
        result = validate_tool_arguments("list_schemas", {"noop": "doit"})
        assert result == {"noop": "doit"}

    def test_list_schemas_missing_required_arg(self):
        """list_schemas without required 'noop' should fail"""
        with pytest.raises(ToolValidationError, match="Invalid arguments"):
            validate_tool_arguments("list_schemas", {})

    def test_get_object_details_valid_args(self):
        """get_object_details with all required args should pass"""
        args = {
            "schema_name": "public",
            "object_name": "users",
            "object_type": "table"
        }
        result = validate_tool_arguments("get_object_details", args)
        assert result == args

    def test_get_object_details_default_type(self):
        """get_object_details should apply default object_type"""
        args = {"schema_name": "public", "object_name": "users"}
        result = validate_tool_arguments("get_object_details", args)
        assert result["schema_name"] == "public"
        assert result["object_name"] == "users"
        assert result["object_type"] == "table"  # Default value

    def test_get_top_queries_type_coercion(self):
        """get_top_queries should coerce types"""
        args = {"limit": "10"}  # String instead of int
        result = validate_tool_arguments("get_top_queries", args)
        assert result["limit"] == 10  # Coerced to int

    def test_get_top_queries_range_validation(self):
        """get_top_queries should enforce value ranges"""
        # Limit must be >= 1 and <= 100
        args = {"limit": 150}
        with pytest.raises(ToolValidationError, match="Invalid arguments"):
            validate_tool_arguments("get_top_queries", args)

    def test_get_top_queries_default_values(self):
        """get_top_queries should apply default values"""
        args = {}
        result = validate_tool_arguments("get_top_queries", args)
        assert result["sort_by"] == "resources"  # Default value
        assert result["limit"] == 10  # Default value


class TestCompleteValidation:
    """Tests for complete tool call validation (name + arguments)"""

    def test_valid_tool_call(self):
        """Complete valid tool call should pass"""
        tool_name = "execute_sql"
        args = {"sql": "SELECT * FROM users"}
        result = validate_tool_call(tool_name, args)
        assert result["sql"] == "SELECT * FROM users"

    def test_invalid_tool_name_rejected(self):
        """Tool call with unknown tool should be rejected"""
        with pytest.raises(ToolValidationError, match="not in the approved allowlist"):
            validate_tool_call("evil_tool", {"arg": "value"})

    def test_invalid_arguments_rejected(self):
        """Tool call with invalid arguments should be rejected"""
        with pytest.raises(ToolValidationError, match="Invalid arguments"):
            validate_tool_call("list_schemas", {"wrong_arg": "value"})


class TestMCPServerToolCheck:
    """Tests for MCP server tool list validation"""

    def test_matching_tools(self, caplog):
        """MCP server with matching tools should log success"""
        import logging
        caplog.set_level(logging.INFO)
        advertised = list(ALLOWED_TOOLS)
        check_mcp_server_tools(advertised)
        assert "matches allowlist" in caplog.text

    def test_unknown_tools_warning(self, caplog):
        """MCP server advertising unknown tools should log warning"""
        advertised = list(ALLOWED_TOOLS) + ["suspicious_tool"]
        check_mcp_server_tools(advertised)
        assert "not in allowlist" in caplog.text
        assert "suspicious_tool" in caplog.text

    def test_missing_tools_warning(self, caplog):
        """MCP server missing expected tools should log warning"""
        advertised = ["execute_sql", "list_schemas"]  # Missing most tools
        check_mcp_server_tools(advertised)
        assert "not advertised by MCP server" in caplog.text


# Example test data for integration testing
VALID_TOOL_CALLS = [
    ("execute_sql", {"sql": "SELECT 1"}),
    ("list_schemas", {"noop": "doit"}),
    ("list_objects", {"schema_name": "public"}),
    ("get_object_details", {"schema_name": "public", "object_name": "users"}),
    ("explain_query", {"sql": "SELECT * FROM users", "analyze": False}),
    ("get_top_queries", {"limit": 10}),
    ("analyze_workload_indexes", {"max_index_size_mb": 5000}),
    ("analyze_query_indexes", {"queries": ["SELECT * FROM users"]}),
    ("analyze_db_health", {"health_type": "all"}),
]

INVALID_TOOL_CALLS = [
    ("_internal_function", {}),  # Unauthorized tool
    ("drop_database", {"name": "production"}),  # Unauthorized tool
    ("list_schemas", {}),  # Missing required argument
    ("get_object_details", {}),  # Missing required arguments
]


@pytest.mark.parametrize("tool_name,args", VALID_TOOL_CALLS)
def test_all_valid_tools(tool_name, args):
    """Parameterized test for all valid tool calls"""
    result = validate_tool_call(tool_name, args)
    assert isinstance(result, dict)


@pytest.mark.parametrize("tool_name,args", INVALID_TOOL_CALLS)
def test_all_invalid_tools(tool_name, args):
    """Parameterized test for all invalid tool calls"""
    with pytest.raises(ToolValidationError):
        validate_tool_call(tool_name, args)
