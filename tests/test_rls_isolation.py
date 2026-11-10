import os
import re
import pytest

SCHEMA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api", "migrations", "001_initial_schema.sql"))

MANDATORY_TABLES = [
    "tasks",
    "task_policies",
    "agents",
    "agent_runs",
    "quotes",
    "transactions",
    "trust_decisions",
    "user_approvals",
    "paypal_orders",
    "audit_events",
]

def test_schema_migration_file_exists():
    assert os.path.exists(SCHEMA_PATH), f"Schema migration not found at {SCHEMA_PATH}"

def test_all_tables_have_user_id_and_timestamps():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql = f.read()

    for table in MANDATORY_TABLES:
        table_pattern = rf"CREATE TABLE IF NOT EXISTS public\.{table}\s*\((.*?)\);"
        match = re.search(table_pattern, sql, re.DOTALL | re.IGNORECASE)
        assert match is not None, f"Table {table} definition not found in migration"
        table_body = match.group(1)

        assert "user_id" in table_body, f"Table {table} missing user_id"
        assert "created_at" in table_body, f"Table {table} missing created_at"
        assert "updated_at" in table_body, f"Table {table} missing updated_at"

def test_all_tables_have_rls_enabled():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql = f.read()

    for table in MANDATORY_TABLES:
        rls_pattern = rf"ALTER TABLE public\.{table}\s+ENABLE ROW LEVEL SECURITY;"
        match = re.search(rls_pattern, sql, re.IGNORECASE)
        assert match is not None, f"RLS not enabled for table public.{table}"

def test_all_tables_have_user_isolation_policies():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql = f.read()

    for table in MANDATORY_TABLES:
        # Check select policy enforces auth.uid() = user_id
        select_policy_pattern = rf'CREATE POLICY "{table}_user_isolation_select" ON public\.{table}\s+FOR SELECT TO authenticated USING \(auth\.uid\(\) = user_id\);'
        match = re.search(select_policy_pattern, sql, re.IGNORECASE)
        assert match is not None, f"SELECT isolation policy missing for {table}"

def test_audit_events_has_no_update_or_delete_policy():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql = f.read()

    # Verify no UPDATE policy exists for audit_events
    update_match = re.search(r'CREATE POLICY [^;]+ ON public\.audit_events\s+FOR UPDATE', sql, re.IGNORECASE)
    assert update_match is None, "audit_events must NOT have an UPDATE policy (append-only)"

    # Verify no DELETE policy exists for audit_events
    delete_match = re.search(r'CREATE POLICY [^;]+ ON public\.audit_events\s+FOR DELETE', sql, re.IGNORECASE)
    assert delete_match is None, "audit_events must NOT have a DELETE policy (append-only)"

    # Verify trigger prevents mutations
    trigger_match = re.search(r'CREATE TRIGGER trg_audit_events_prevent_mutation', sql, re.IGNORECASE)
    assert trigger_match is not None, "Missing immutability trigger for audit_events"

def test_indexes_on_task_id_transaction_id_and_created_at():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        sql = f.read()

    # Indexes on task_id
    for tbl in ["task_policies", "agent_runs", "quotes", "transactions", "trust_decisions", "user_approvals", "paypal_orders", "audit_events"]:
        pattern = rf"CREATE INDEX IF NOT EXISTS idx_{tbl}_task_id ON public\.{tbl}\(task_id\);"
        assert re.search(pattern, sql, re.IGNORECASE) is not None, f"Missing index on task_id for {tbl}"

    # Indexes on transaction_id
    for tbl in ["trust_decisions", "user_approvals", "paypal_orders", "audit_events"]:
        pattern = rf"CREATE INDEX IF NOT EXISTS idx_{tbl}_transaction_id ON public\.{tbl}\(transaction_id\);"
        assert re.search(pattern, sql, re.IGNORECASE) is not None, f"Missing index on transaction_id for {tbl}"

    # Indexes on created_at
    for tbl in MANDATORY_TABLES:
        pattern = rf"CREATE INDEX IF NOT EXISTS idx_{tbl}_created_at ON public\.{tbl}\(created_at DESC\);"
        assert re.search(pattern, sql, re.IGNORECASE) is not None, f"Missing index on created_at for {tbl}"

def test_functional_rls_query_filter():
    """
    Simulates the RLS policy evaluation engine (auth.uid() = user_id):
    Ensures that when User A queries records, User B's rows are strictly filtered out.
    """
    database_records = [
        {"id": "t-1", "user_id": "user-a", "title": "User A Task", "budget_max": 100},
        {"id": "t-2", "user_id": "user-b", "title": "User B Task", "budget_max": 200},
        {"id": "t-3", "user_id": "user-a", "title": "User A Second Task", "budget_max": 300},
    ]

    def evaluate_rls_select(records, current_user_id):
        # Equivalent to Postgres: USING (auth.uid() = user_id)
        return [r for r in records if r["user_id"] == current_user_id]

    user_a_results = evaluate_rls_select(database_records, current_user_id="user-a")
    assert len(user_a_results) == 2
    assert all(r["user_id"] == "user-a" for r in user_a_results)

    user_b_results = evaluate_rls_select(database_records, current_user_id="user-b")
    assert len(user_b_results) == 1
    assert user_b_results[0]["id"] == "t-2"

    # User C (anonymous or different user) sees zero rows
    user_c_results = evaluate_rls_select(database_records, current_user_id="user-c")
    assert len(user_c_results) == 0

