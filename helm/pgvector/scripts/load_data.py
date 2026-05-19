#!/usr/bin/env python3
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
import sys
import time
from typing import List, Tuple

def wait_for_postgres(host, user, password, dbname, max_retries=30):
    """Wait for PostgreSQL to be ready."""
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port="5432",
            )
            conn.close()
            print(f"PostgreSQL is ready!")
            return True
        except psycopg2.OperationalError as e:
            print(f"Waiting for PostgreSQL... (attempt {i+1}/{max_retries})")
            time.sleep(2)

    print("PostgreSQL did not become ready in time")
    return False

def create_schema(conn):
    """Create all tables and views."""
    cursor = conn.cursor()

    # Create dim_customer table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dim_customer (
            customer_id VARCHAR(50) PRIMARY KEY,
            customer_unique_id VARCHAR(50),
            customer_city VARCHAR(100),
            customer_state CHAR(2)
        );
    """)

    cursor.execute("""
        COMMENT ON TABLE dim_customer IS
        'Core customer table. CONTAINS PII (PCI, address). DO NOT USE FOR general BI. Only for auth_service.';
    """)

    # Create fact_orders table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_orders (
            order_id VARCHAR(50) PRIMARY KEY,
            customer_id VARCHAR(50),
            order_purchase_timestamp TIMESTAMP,
            order_status VARCHAR(20)
        );
    """)

    # Create fact_order_payments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fact_order_payments (
            order_id VARCHAR(50) NOT NULL,
            payment_sequential SMALLINT NOT NULL,
            payment_type VARCHAR(50),
            payment_installments SMALLINT,
            payment_value NUMERIC(10, 2) NOT NULL,
            CONSTRAINT pk_fact_order_payments PRIMARY KEY (order_id, payment_sequential),
            CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES fact_orders (order_id),
            CHECK (payment_value >= 0),
            CHECK (payment_installments IS NULL OR payment_installments >= 0)
        );
    """)

    conn.commit()
    print("Schema created successfully")

def create_views(conn):
    """Create all views."""
    cursor = conn.cursor()

    # Create deprecated table (sample)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_master_DEPRECATED AS
        SELECT * FROM dim_customer TABLESAMPLE BERNOULLI (50);
    """)

    # Create deprecated view
    cursor.execute("""
        CREATE OR REPLACE VIEW sales_rpt_v2 AS
        SELECT * FROM fact_orders WHERE order_purchase_timestamp < '2018-01-01';
    """)

    # Create old LTV view (deprecated)
    cursor.execute("""
        CREATE OR REPLACE VIEW v_cust_ltv_agg_DEPRECATED AS
        SELECT
            t1.customer_unique_id,
            SUM(t3.payment_value) as total_revenue,
            TO_CHAR(MIN(t2.order_purchase_timestamp), 'YYYY-MM-DD') AS first_purchase_date,
            TO_CHAR(MAX(t2.order_purchase_timestamp), 'YYYY-MM-DD') AS last_purchase_date
        FROM
            dim_customer AS t1
        JOIN
            fact_orders AS t2 ON t1.customer_id = t2.customer_id
        JOIN
            fact_order_payments AS t3 ON t2.order_id = t3.order_id
        WHERE
            t2.order_status = 'delivered'
            AND t2.order_purchase_timestamp < '2018-01-01'
        GROUP BY
            t1.customer_unique_id;
    """)

    cursor.execute("""
        COMMENT ON VIEW v_cust_ltv_agg_DEPRECATED IS
        '[DEPRECATED] Old LTV calculation. Only includes data before 2018. DEPRECATED as of Q3 2024. Do not use for new reporting. Use v_rpt_customer_ltv_certified instead.';
    """)

    # Create certified LTV view
    cursor.execute("""
        CREATE OR REPLACE VIEW v_rpt_customer_ltv_certified AS
        SELECT
            c.customer_unique_id,
            c.customer_city,
            c.customer_state,
            SUM(p.payment_value) AS total_revenue_ltv,
            COUNT(DISTINCT o.order_id) AS total_orders,
            AVG(p.payment_value) AS average_order_value,
            TO_CHAR(MIN(o.order_purchase_timestamp), 'YYYY-MM-DD') AS first_purchase_date,
            TO_CHAR(MAX(o.order_purchase_timestamp), 'YYYY-MM-DD') AS last_purchase_date
        FROM
            dim_customer AS c
        JOIN
            fact_orders AS o ON c.customer_id = o.customer_id
        JOIN
            fact_order_payments AS p ON o.order_id = p.order_id
        WHERE
            o.order_status = 'delivered'
        GROUP BY
            c.customer_unique_id,
            c.customer_city,
            c.customer_state;
    """)

    cursor.execute("""
        COMMENT ON VIEW v_rpt_customer_ltv_certified IS
        '[CERTIFIED] Gold-standard, PII-scrubbed view for all customer LTV reporting. Aggregated daily. Maintained by: Finance BI Team';
    """)

    conn.commit()
    print("Views created successfully")

def populate_dim_customer(conn, csv_path):
    """Load customer dimension data."""
    print(f"Loading customers from {csv_path}...")
    df = pd.read_csv(csv_path)

    cols_list = ["customer_id", "customer_unique_id", "customer_city", "customer_state"]
    df = df[cols_list].dropna()
    df = df.replace({pd.NA: None, pd.NaT: None})
    df = df.where(pd.notnull(df), None)

    tuples = [tuple(x) for x in df.to_numpy()]
    cols = ",".join(cols_list)
    placeholders = ",".join(["%s"] * len(cols_list))
    query = f"INSERT INTO dim_customer ({cols}) VALUES ({placeholders}) ON CONFLICT (customer_id) DO NOTHING"

    cursor = conn.cursor()
    execute_batch(cursor, query, tuples, page_size=1000)
    conn.commit()
    print(f"Loaded {len(tuples)} customers")

def populate_fact_orders(conn, csv_path):
    """Load orders fact data."""
    print(f"Loading orders from {csv_path}...")
    df = pd.read_csv(csv_path)

    cols_list = ["order_id", "customer_id", "order_purchase_timestamp", "order_status"]
    df = df[cols_list].dropna()
    df = df.replace({pd.NA: None, pd.NaT: None})
    df = df.where(pd.notnull(df), None)

    tuples = [tuple(x) for x in df.to_numpy()]
    cols = ",".join(cols_list)
    placeholders = ",".join(["%s"] * len(cols_list))
    query = f"INSERT INTO fact_orders ({cols}) VALUES ({placeholders}) ON CONFLICT (order_id) DO NOTHING"

    cursor = conn.cursor()
    execute_batch(cursor, query, tuples, page_size=1000)
    conn.commit()
    print(f"Loaded {len(tuples)} orders")

def populate_fact_order_payments(conn, csv_path):
    """Load order payments fact data."""
    print(f"Loading payments from {csv_path}...")
    df = pd.read_csv(csv_path)

    cols_list = ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"]
    df = df[cols_list].dropna()
    df = df.replace({pd.NA: None, pd.NaT: None})
    df = df.where(pd.notnull(df), None)

    tuples = [tuple(x) for x in df.to_numpy()]
    cols = ",".join(cols_list)
    placeholders = ",".join(["%s"] * len(cols_list))
    query = f"INSERT INTO fact_order_payments ({cols}) VALUES ({placeholders}) ON CONFLICT (order_id, payment_sequential) DO NOTHING"

    cursor = conn.cursor()
    execute_batch(cursor, query, tuples, page_size=1000)
    conn.commit()
    print(f"Loaded {len(tuples)} payment records")

def create_readonly_user(conn, readonly_password):
    """
    Create read-only database user for MCP server.

    This user has SELECT access to tables/views but cannot modify data or schema.
    Purpose: Defense-in-depth security - limits blast radius if MCP server is compromised.

    Note: Does NOT auto-grant on future tables - privileges must be re-granted if schema changes.
    """
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute("SELECT 1 FROM pg_catalog.pg_user WHERE usename = 'mcp_readonly'")
    user_exists = cursor.fetchone() is not None

    if not user_exists:
        # Create user with password
        cursor.execute(f"CREATE USER mcp_readonly WITH PASSWORD %s", (readonly_password,))
        print("Created user: mcp_readonly")
    else:
        # Update password for existing user
        cursor.execute(f"ALTER USER mcp_readonly WITH PASSWORD %s", (readonly_password,))
        print("Updated password for existing user: mcp_readonly")

    # Grant connection to database
    cursor.execute("GRANT CONNECT ON DATABASE postgres TO mcp_readonly")

    # Grant schema usage
    cursor.execute("GRANT USAGE ON SCHEMA public TO mcp_readonly")

    # Grant SELECT on all existing tables and views
    cursor.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_readonly")

    # Grant SELECT on all existing sequences
    cursor.execute("GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO mcp_readonly")

    # Grant pg_read_all_stats role for query analysis tools
    cursor.execute("GRANT pg_read_all_stats TO mcp_readonly")

    conn.commit()
    print("✅ Read-only user configured successfully")
    print("   - Can: SELECT from existing tables/views, read system catalogs, run EXPLAIN, read pg_stat_statements")
    print("   - Cannot: INSERT/UPDATE/DELETE data, CREATE/ALTER/DROP schema, run COMMENT ON")
    print("   - Note: If new tables are added, re-run this script to grant SELECT on them")

def main():
    import os

    host = os.environ.get("POSTGRES_HOST", "pgvector-postgres-service")
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    dbname = os.environ.get("POSTGRES_DB")
    readonly_password = os.environ.get("POSTGRES_READONLY_PASSWORD")

    # Validate required environment variables
    if not readonly_password:
        print("ERROR: POSTGRES_READONLY_PASSWORD environment variable is required")
        sys.exit(1)

    print(f"Connecting to PostgreSQL at {host}...")

    if not wait_for_postgres(host, user, password, dbname):
        sys.exit(1)

    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port="5432",
    )

    try:
        print("Creating schema...")
        create_schema(conn)

        print("Loading data...")
        populate_dim_customer(conn, "/data/olist_customers_dataset.csv")
        populate_fact_orders(conn, "/data/olist_orders_dataset.csv")
        populate_fact_order_payments(conn, "/data/olist_order_payments_dataset.csv")

        print("Creating views...")
        create_views(conn)

        print("Creating read-only user for MCP server...")
        create_readonly_user(conn, readonly_password)

        print("Data loading complete!")

    except Exception as e:
        print(f"Error loading data: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
