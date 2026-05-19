# Read-Only Database User Implementation

## Overview

The MCP server now connects to PostgreSQL using a **read-only user** (`mcp_readonly`) instead of the `postgres` superuser. This provides **defense-in-depth security** by limiting the blast radius if the MCP server is compromised.

## Changes Made

### 1. Database User Creation
**File:** `helm/pgvector/scripts/load_data.py`
- Added `create_readonly_user()` function
- Creates `mcp_readonly` user with password from `POSTGRES_READONLY_PASSWORD` env var
- Grants appropriate privileges after schema and data are loaded

### 2. MCP Server Configuration
**File:** `helm/pg-airman-mcp/values.yaml`
- Changed `postgres.user` from `postgres` to `mcp_readonly`
- Updated comments to reflect security purpose

### 3. Documentation
**Files:** 
- `helm/pgvector/scripts/create_readonly_user.sql` - SQL reference script
- `DATABASE_USER_PRIVILEGE_ANALYSIS.md` - Full privilege analysis

## User Privileges

### ✅ What `mcp_readonly` CAN Do

| Capability | Purpose | MCP Tools Enabled |
|-----------|---------|-------------------|
| `SELECT` on existing tables/views | Read data | `execute_sql` (SELECT only) |
| Read system catalogs | List schemas, tables, columns | `list_schemas`, `list_objects`, `get_object_details` |
| Read `pg_stat_statements` | Query analysis | `get_top_queries`, `analyze_workload_indexes` |
| `EXPLAIN` queries | Query planning | `explain_query` |

### ❌ What `mcp_readonly` CANNOT Do

| Blocked Action | Security Benefit |
|----------------|------------------|
| `INSERT`, `UPDATE`, `DELETE` | Cannot modify data |
| `CREATE`, `ALTER`, `DROP` | Cannot modify schema |
| `TRUNCATE` | Cannot delete table contents |
| `COMMENT ON` | Cannot add governance metadata (requires ownership) |
| Create extensions, roles | Cannot perform admin operations |

## MCP Tools Impact

### Working Tools (8 of 9)
1. ✅ `execute_sql` - SELECT queries only (restricted mode still applies)
2. ✅ `list_schemas` - Read from `information_schema`
3. ✅ `list_objects` - Read from `pg_catalog`
4. ✅ `get_object_details` - Read from `pg_catalog`
5. ✅ `explain_query` - EXPLAIN command (requires SELECT on tables)
6. ✅ `analyze_workload_indexes` - Read from `pg_stat_statements`
7. ✅ `get_top_queries` - Read from `pg_stat_statements`
8. ✅ Read existing comments - System catalogs are world-readable

### Disabled Tools (1 of 9)
1. ❌ `add_comment_to_object` - Requires table ownership or superuser privilege

**Note:** The `add_comment_to_object` tool will fail with a permission error. Users can still **read** existing governance comments through other tools, but cannot **add** new ones via the copilot.

## Deployment Instructions

### Prerequisites
The `POSTGRES_READONLY_PASSWORD` is **required** and must be provided during deployment.

**IMPORTANT:** If the password is not provided, the data loader job will fail with an error.

### Deploy Command

The Makefile now requires `postgres.readonlyPassword` as a parameter:

```bash
make install \
  NAMESPACE=your-namespace \
  postgres.userId=postgres \
  postgres.password=<superuser-password> \
  postgres.databaseName=postgres \
  postgres.readonlyPassword=<readonly-user-password>
```

**Deploy Order:**
1. **pgvector** chart deploys and runs `load_data.py` which creates both the schema and the `mcp_readonly` user
2. **pg-airman-mcp** chart deploys and connects using `mcp_readonly` user (hardcoded in Makefile)

### Verification
After deployment, test that MCP tools work:

```bash
# Query the copilot - should work
"Show me all schemas in the database"
"List tables in the public schema"
"What are the top 10 slowest queries?"

# This will fail - expected behavior
"Add a comment to the dim_customer table saying 'PII data'"
# Expected error: permission denied for table dim_customer
```

### Important: Adding New Tables

**Note:** The `mcp_readonly` user does NOT automatically receive SELECT privileges on new tables.

If you add new tables to the database after initial deployment, you must re-grant privileges:

```sql
-- Connect as postgres superuser
GRANT SELECT ON new_table_name TO mcp_readonly;

-- Or re-grant on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;
```

Alternatively, re-run the data loader job (which will re-execute the `create_readonly_user()` function).

## Security Improvement Summary

| Before | After |
|--------|-------|
| MCP server uses `postgres` superuser | MCP server uses `mcp_readonly` limited user |
| Can modify data/schema (blocked by app-level filtering) | **Cannot** modify data/schema (DB-level enforcement) |
| Single layer of defense (restricted mode) | **Multiple layers** (restricted mode + DB privileges) |
| High risk if MCP server compromised | **Low risk** - readonly user limits damage |

## Workarounds for Adding Comments

If users need to add governance comments, use one of these approaches:

### Option 1: Manual SQL (Recommended)
Connect as `postgres` superuser and run:
```sql
COMMENT ON TABLE dim_customer IS 'Contains PII data';
```

### Option 2: Separate Admin Script
Create a dedicated admin tool/script that connects with elevated privileges for governance metadata updates.

### Option 3: Security Definer Function (Future Enhancement)
Implement a stored procedure that runs with owner privileges - requires custom MCP server code changes.

## Rollback Instructions

If you need to revert to superuser access:

1. Update `helm/pg-airman-mcp/values.yaml`:
   ```yaml
   postgres:
     user: postgres
     password: <postgres superuser password>
   ```

2. Redeploy pg-airman-mcp chart

**Note:** The `mcp_readonly` user will remain in the database but won't be used.
