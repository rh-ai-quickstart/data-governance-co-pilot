# Database User Privilege Analysis for MCP Server

## Current Situation

**Current Setup:**
- MCP server connects as: `postgres` (superuser)
- Access mode: `restricted` (limits SQL execution)
- Database: Contains tables, views, and comments for governance

## Your Idea: Restricted Database User

**Goal:** Create a limited-privilege user for the MCP server that can:
1. ✅ Read (SELECT) from specific tables/views
2. ✅ Add/update COMMENT on tables, views, columns
3. ❌ Cannot modify data (INSERT, UPDATE, DELETE)
4. ❌ Cannot modify schema (CREATE, ALTER, DROP)

---

## Why It's More Complex Than Just SELECT

You're absolutely right - it's not as simple as granting SELECT. Here's why:

### 1. **MCP Tools Require Different Privilege Levels**

| Tool | SQL Operations | Privileges Required |
|------|----------------|---------------------|
| `execute_sql` | `SELECT` only | `SELECT` on tables/views |
| `list_schemas` | Query `information_schema` or `pg_catalog` | `USAGE` on schema + metadata access |
| `list_objects` | Query `pg_class`, `pg_namespace`, `pg_description` | Read access to system catalogs |
| `get_object_details` | Query `pg_attribute`, `pg_constraint`, `pg_description` | Read access to system catalogs |
| `explain_query` | `EXPLAIN` command | `SELECT` privilege on queried tables |
| `add_comment_to_object` | `COMMENT ON` command | **Owner or specific COMMENT privilege** |
| `analyze_workload_indexes` | Query `pg_stat_statements` | `pg_read_all_stats` role or specific grants |
| `get_top_queries` | Query `pg_stat_statements` | `pg_read_all_stats` role |

### 2. **System Catalog Access Requirements**

**Problem:** To list schemas, tables, and read comments, the MCP server queries:
- `pg_catalog.pg_class` - table/view definitions
- `pg_catalog.pg_attribute` - column definitions
- `pg_catalog.pg_namespace` - schema information
- `pg_catalog.pg_description` - comments
- `pg_catalog.pg_constraint` - constraints/foreign keys
- `pg_catalog.pg_stat_statements` - query statistics

**Default Behavior:**
- These catalogs are world-readable in PostgreSQL
- Any authenticated user can query them
- No special grants needed for read-only access

**Implication:** ✅ A non-superuser can read all metadata

### 3. **COMMENT Privilege Complexity**

**PostgreSQL COMMENT Behavior:**
```sql
COMMENT ON TABLE my_table IS 'Some comment';
```

**Who can run this?**
- ✅ Superuser (postgres)
- ✅ Table owner
- ❌ Regular user (even with all other privileges)

**Problem:** PostgreSQL doesn't have a `GRANT COMMENT` privilege!

**Workarounds:**
1. **Make user the owner** (too broad - can ALTER/DROP)
2. **Use security definer function** (call function that runs as owner)
3. **Grant table ownership selectively** (complex to manage)
4. **Accept read-only limitation** (disable `add_comment_to_object`)

### 4. **pg_stat_statements Extension**

**For tools like `get_top_queries` and `analyze_workload_indexes`:**

```sql
SELECT query, calls, total_exec_time 
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

**Privileges Required:**
- `pg_read_all_stats` role (PostgreSQL 10+)
- Or: `GRANT SELECT ON pg_stat_statements TO mcp_user`

**Implication:** ✅ Can be granted without superuser

---

## Recommended Approach: Two-User Strategy

### Option A: Single Restricted User (Simpler, Less Secure)

**Use Case:** Development, testing, low-risk environments

**Privileges:**
```sql
-- Create restricted user
CREATE USER mcp_readonly WITH PASSWORD 'secure_password';

-- Grant connection
GRANT CONNECT ON DATABASE your_db TO mcp_readonly;

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO mcp_readonly;

-- Grant SELECT on all tables and views
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO mcp_readonly;

-- Auto-grant on future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
  GRANT SELECT ON TABLES TO mcp_readonly;

-- Grant stats access
GRANT pg_read_all_stats TO mcp_readonly;
```

**Limitations:**
- ❌ Cannot use `add_comment_to_object` tool
- ✅ Can use all read-only tools
- ✅ Strong security boundary

### Option B: Dual-User Strategy (Recommended for Production)

**Use Case:** Production, compliance, defense-in-depth

**Setup:**
1. **Read-Only User** (mcp_reader) - Default connection
2. **Comment User** (mcp_commenter) - Only for governance metadata updates

**Implementation:**

#### Step 1: Create Read-Only User
```sql
CREATE USER mcp_reader WITH PASSWORD 'reader_pass';
GRANT CONNECT ON DATABASE your_db TO mcp_reader;
GRANT USAGE ON SCHEMA public TO mcp_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_reader;
GRANT pg_read_all_stats TO mcp_reader;

ALTER DEFAULT PRIVILEGES IN SCHEMA public 
  GRANT SELECT ON TABLES TO mcp_reader;
```

#### Step 2: Create Comment User (Owns Nothing, Can Comment)

**Problem:** PostgreSQL requires ownership for COMMENT.

**Solution:** Use security definer function:

```sql
-- Create comment user
CREATE USER mcp_commenter WITH PASSWORD 'commenter_pass';

-- Create security definer function (runs as superuser)
CREATE OR REPLACE FUNCTION public.add_governance_comment(
    p_schema text,
    p_object_type text,
    p_object_name text,
    p_comment text,
    p_column_name text DEFAULT NULL
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER  -- Runs with owner privileges (postgres)
SET search_path = public, pg_catalog  -- Security: prevent search_path attacks
AS $$
DECLARE
    v_sql text;
BEGIN
    -- Whitelist allowed schemas (prevent SQL injection to other schemas)
    IF p_schema NOT IN ('public') THEN
        RAISE EXCEPTION 'Schema % not allowed', p_schema;
    END IF;

    -- Build COMMENT command
    CASE p_object_type
        WHEN 'table' THEN
            v_sql := format('COMMENT ON TABLE %I.%I IS %L', 
                           p_schema, p_object_name, p_comment);
        WHEN 'view' THEN
            v_sql := format('COMMENT ON VIEW %I.%I IS %L', 
                           p_schema, p_object_name, p_comment);
        WHEN 'column' THEN
            IF p_column_name IS NULL THEN
                RAISE EXCEPTION 'column_name required for column comments';
            END IF;
            v_sql := format('COMMENT ON COLUMN %I.%I.%I IS %L', 
                           p_schema, p_object_name, p_column_name, p_comment);
        ELSE
            RAISE EXCEPTION 'Object type % not supported', p_object_type;
    END CASE;

    -- Execute comment
    EXECUTE v_sql;
    
    RETURN format('Comment added to %s %s.%s', p_object_type, p_schema, p_object_name);
END;
$$;

-- Grant execute to commenter user
GRANT EXECUTE ON FUNCTION public.add_governance_comment(text, text, text, text, text) TO mcp_commenter;

-- Optional: Create audit log table
CREATE TABLE public.governance_comment_audit (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    db_user TEXT DEFAULT CURRENT_USER,
    schema_name TEXT,
    object_type TEXT,
    object_name TEXT,
    column_name TEXT,
    comment_text TEXT
);

-- Modify function to log (optional)
```

#### Step 3: Configure MCP Server

**Modify MCP Server to Use Dual Connections:**
- **Primary connection:** `mcp_reader` (read-only)
- **Comment connection:** `mcp_commenter` (only for `add_comment_to_object`)

**Current Limitation:** PG Airman MCP uses single connection URI.

**Solution:** Modify `add_comment_to_object` tool to call the security definer function instead of raw COMMENT SQL.

---

## Security Comparison

| Aspect | Superuser (Current) | Single Restricted | Dual-User Strategy |
|--------|--------------------|--------------------|-------------------|
| **Data Read** | ✅ Full | ✅ Tables only | ✅ Tables only |
| **Data Write** | ❌ Possible (restricted mode blocks) | ✅ Impossible | ✅ Impossible |
| **Schema Modify** | ❌ Possible | ✅ Impossible | ✅ Impossible |
| **System Catalogs** | ✅ Full | ✅ Read-only | ✅ Read-only |
| **Add Comments** | ✅ Yes | ❌ No | ✅ Via function |
| **Defense Depth** | ❌ Low | ✅ Good | ✅✅ Excellent |
| **Bypass Risk** | ❌ High | ✅ Low | ✅ Very Low |

---

## Implementation Complexity

### Option A: Single Read-Only User
**Effort:** ~30 minutes
1. Create SQL script for user + grants
2. Add to `load_data.py` or separate init script
3. Update MCP Helm chart with new credentials
4. Disable `add_comment_to_object` tool or document limitation

**Files to Modify:**
- `helm/pgvector/scripts/create_readonly_user.sql` (NEW)
- `helm/pg-airman-mcp/values.yaml` (update postgres.user)
- `helm/pg-airman-mcp/templates/secret.yaml` (update credentials)

### Option B: Dual-User Strategy
**Effort:** ~2-3 hours
1. Create SQL scripts for both users + security definer function
2. Add audit logging table
3. Modify PG Airman MCP to use function for comments
4. Test comment workflow
5. Document privilege model

**Files to Modify:**
- `helm/pgvector/scripts/create_users.sql` (NEW)
- `helm/pg-airman-mcp/*` (custom fork or config)
- Documentation

---

## Recommended Path Forward

### Phase 1: Single Read-Only User (Do This Now) ✅

**Why:**
- ✅ Simple, immediate security improvement
- ✅ Doesn't require MCP server code changes
- ✅ Blocks all data/schema modifications at DB level
- ✅ 90% of security benefit with 10% of effort

**Trade-off:**
- ⚠️ Lose `add_comment_to_object` tool
- ⚠️ Users can't update governance metadata via copilot
- ✅ Still have read-only governance comments

**Implementation:**
```sql
-- Add to load_data.py or separate init script
CREATE USER mcp_readonly WITH PASSWORD 'change_me';
GRANT CONNECT ON DATABASE postgres TO mcp_readonly;
GRANT USAGE ON SCHEMA public TO mcp_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly;
GRANT pg_read_all_stats TO mcp_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA public 
  GRANT SELECT ON TABLES TO mcp_readonly;
```

### Phase 2: Security Definer Function (Optional, Later)

**When:**
- Users need to update governance comments via copilot
- After testing Phase 1 in production
- If compliance requires audit trail

---

## Additional Considerations

### 1. **Row-Level Security (RLS)**

If you need data masking beyond table-level access:

```sql
-- Enable RLS on sensitive table
ALTER TABLE dim_customer ENABLE ROW LEVEL SECURITY;

-- Policy: mcp_readonly can only see non-PII aggregates
CREATE POLICY mcp_readonly_policy ON dim_customer
  FOR SELECT
  TO mcp_readonly
  USING (false);  -- No direct access

-- Force users through certified views only
GRANT SELECT ON v_rpt_customer_ltv_certified TO mcp_readonly;
```

### 2. **Connection Pooling**

**Current:** Each MCP pod has direct connection.

**Consider:** PgBouncer or built-in connection pooling to limit connection count.

### 3. **Audit Logging**

Enable PostgreSQL audit logging for the MCP user:

```sql
-- Install pgaudit extension
CREATE EXTENSION IF NOT EXISTS pgaudit;

-- Log all queries from mcp_readonly
ALTER ROLE mcp_readonly SET pgaudit.log = 'read, write, ddl';
```

### 4. **Credential Rotation**

**Current:** Password in Helm values/secrets.

**Better:** Kubernetes ExternalSecret + Vault or AWS Secrets Manager.

---

## Summary & Recommendation

**Your Instinct is Correct:** Least privilege is critical for production.

**Simplest Secure Approach:**
1. ✅ Create `mcp_readonly` user with SELECT-only
2. ✅ Grant `pg_read_all_stats` for query analysis tools
3. ✅ Auto-grant on future tables
4. ⚠️ Accept that `add_comment_to_object` won't work (or make read-only)
5. ✅ Update MCP Helm chart to use new user

**Effort:** 30-60 minutes
**Security Improvement:** Massive (blocks all writes at DB level)

**For Maximum Security:**
- Add security definer function for governance comments
- Implement RLS for row-level data masking
- Enable audit logging
- Use external secret management

---

## Next Steps

Would you like me to:
1. ✅ Create the SQL script for `mcp_readonly` user?
2. ✅ Update `load_data.py` to create the user?
3. ✅ Modify MCP Helm chart to use new credentials?
4. ⚠️ Create security definer function for comments?

Let me know which phase you'd like to implement!

