-- Create read-only database user for MCP server
-- This user has SELECT access to tables/views but cannot modify data or schema
-- Purpose: Defense-in-depth security - limits blast radius if MCP server is compromised

-- Create user (password will be provided via ALTER USER in load_data.py)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'mcp_readonly') THEN
        CREATE USER mcp_readonly;
        RAISE NOTICE 'Created user: mcp_readonly';
    ELSE
        RAISE NOTICE 'User mcp_readonly already exists';
    END IF;
END
$$;

-- Grant connection to database
GRANT CONNECT ON DATABASE postgres TO mcp_readonly;

-- Grant schema usage (required to access objects in the schema)
GRANT USAGE ON SCHEMA public TO mcp_readonly;

-- Grant SELECT on all existing tables and views in public schema
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;

-- Grant SELECT on all existing sequences (for serial columns, etc.)
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO mcp_readonly;

-- NOTE: Does NOT auto-grant on future tables
-- If new tables are added, re-run this script or manually grant:
--   GRANT SELECT ON TABLE new_table TO mcp_readonly;

-- Grant pg_read_all_stats role for query analysis tools (pg_stat_statements, etc.)
-- This enables tools like: get_top_queries, analyze_workload_indexes
GRANT pg_read_all_stats TO mcp_readonly;

-- Summary of what mcp_readonly CAN do:
-- ✅ Connect to database
-- ✅ Read all existing tables and views in public schema
-- ✅ Read system catalogs (pg_catalog.* - world-readable by default)
-- ✅ Read query statistics (pg_stat_statements)
-- ✅ Run EXPLAIN on queries (requires SELECT privilege on queried tables)

-- Summary of what mcp_readonly CANNOT do:
-- ❌ INSERT, UPDATE, DELETE data
-- ❌ CREATE, ALTER, DROP tables/views/schemas
-- ❌ TRUNCATE tables
-- ❌ Run COMMENT ON (requires ownership or superuser)
-- ❌ Access tables in other schemas (unless explicitly granted)
-- ❌ Create extensions, modify roles, or other admin operations
-- ❌ Automatically access new tables (privileges must be re-granted)
