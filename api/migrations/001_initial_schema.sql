-- ==============================================================================
-- Nirbhar AI — Phase 1 Supabase Schema Migration
-- Tables: tasks, task_policies, agents, agent_runs, quotes, transactions,
--         trust_decisions, user_approvals, paypal_orders, audit_events
-- Enforces: Strict Row Level Security (RLS) & Immutable Append-Only Audit Ledger
-- ==============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ------------------------------------------------------------------------------
-- 1. tasks
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    budget_max NUMERIC(12, 2) NOT NULL CHECK (budget_max > 0),
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED', 'CANCELLED', 'FAILED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 2. task_policies
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.task_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    auto_approve_threshold NUMERIC(12, 2) NOT NULL DEFAULT 50.00 CHECK (auto_approve_threshold >= 0),
    single_tx_limit NUMERIC(12, 2) NOT NULL DEFAULT 200.00 CHECK (single_tx_limit >= auto_approve_threshold),
    allowed_domains JSONB NOT NULL DEFAULT '[]'::jsonb,
    blacklisted_domains JSONB NOT NULL DEFAULT '[]'::jsonb,
    strict_mode BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_task_policy UNIQUE (task_id)
);

-- ------------------------------------------------------------------------------
-- 3. agents
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('coordinator', 'research', 'service')),
    public_key TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_agent_role UNIQUE (user_id, role)
);

-- ------------------------------------------------------------------------------
-- 4. agent_runs
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES public.agents(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    prompt_tokens INT DEFAULT 0,
    completion_tokens INT DEFAULT 0,
    latency_ms NUMERIC(10, 2) DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'STARTED' CHECK (status IN ('STARTED', 'COMPLETED', 'FAILED')),
    output_payload JSONB DEFAULT '{}'::jsonb,
    signature TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 5. quotes
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.quotes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    agent_id UUID REFERENCES public.agents(id) ON DELETE SET NULL,
    vendor_name TEXT NOT NULL,
    quote_url TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'USD',
    quote_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 6. transactions
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    quote_id UUID REFERENCES public.quotes(id) ON DELETE SET NULL,
    amount NUMERIC(12, 2) NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'NEEDS_HUMAN_APPROVAL', 'BLOCKED', 'EXECUTING', 'COMPLETED', 'FAILED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 7. trust_decisions
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.trust_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES public.transactions(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    decision TEXT NOT NULL CHECK (decision IN ('APPROVED', 'NEEDS_HUMAN_APPROVAL', 'BLOCKED')),
    rules_evaluated JSONB NOT NULL DEFAULT '[]'::jsonb,
    risk_score NUMERIC(5, 2) DEFAULT 0.0,
    decision_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 8. user_approvals
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.user_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES public.transactions(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED')),
    approved_at TIMESTAMPTZ,
    user_signature TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 9. paypal_orders
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.paypal_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL REFERENCES public.transactions(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES public.tasks(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    paypal_order_id TEXT NOT NULL UNIQUE,
    paypal_capture_id TEXT,
    environment TEXT NOT NULL DEFAULT 'sandbox',
    status TEXT NOT NULL,
    raw_order_payload JSONB,
    raw_capture_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- 10. audit_events (Append-Only Tamper-Evident Chain)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    task_id UUID REFERENCES public.tasks(id) ON DELETE SET NULL,
    transaction_id UUID REFERENCES public.transactions(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    sequence_number BIGINT NOT NULL,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------
-- INDEXES: On task_id, transaction_id, created_at
-- ------------------------------------------------------------------------------
-- task_id indexes
CREATE INDEX IF NOT EXISTS idx_task_policies_task_id ON public.task_policies(task_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_task_id ON public.agent_runs(task_id);
CREATE INDEX IF NOT EXISTS idx_quotes_task_id ON public.quotes(task_id);
CREATE INDEX IF NOT EXISTS idx_transactions_task_id ON public.transactions(task_id);
CREATE INDEX IF NOT EXISTS idx_trust_decisions_task_id ON public.trust_decisions(task_id);
CREATE INDEX IF NOT EXISTS idx_user_approvals_task_id ON public.user_approvals(task_id);
CREATE INDEX IF NOT EXISTS idx_paypal_orders_task_id ON public.paypal_orders(task_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_task_id ON public.audit_events(task_id);

-- transaction_id indexes
CREATE INDEX IF NOT EXISTS idx_trust_decisions_transaction_id ON public.trust_decisions(transaction_id);
CREATE INDEX IF NOT EXISTS idx_user_approvals_transaction_id ON public.user_approvals(transaction_id);
CREATE INDEX IF NOT EXISTS idx_paypal_orders_transaction_id ON public.paypal_orders(transaction_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_transaction_id ON public.audit_events(transaction_id);

-- created_at indexes
CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON public.tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_policies_created_at ON public.task_policies(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agents_created_at ON public.agents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at ON public.agent_runs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_created_at ON public.quotes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON public.transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trust_decisions_created_at ON public.trust_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_approvals_created_at ON public.user_approvals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_paypal_orders_created_at ON public.paypal_orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON public.audit_events(created_at DESC);

-- audit_events chain indexing
CREATE UNIQUE INDEX IF NOT EXISTS idx_audit_events_user_seq ON public.audit_events(user_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_audit_events_hash ON public.audit_events(hash);

-- ------------------------------------------------------------------------------
-- IMMUTABILITY GUARD FOR audit_events (NO UPDATE, NO DELETE)
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.prevent_audit_events_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'SECURITY ERROR: audit_events is an immutable, append-only ledger. Update and Delete operations are strictly forbidden.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_events_prevent_mutation ON public.audit_events;
CREATE TRIGGER trg_audit_events_prevent_mutation
BEFORE UPDATE OR DELETE ON public.audit_events
FOR EACH ROW EXECUTE FUNCTION public.prevent_audit_events_mutation();

-- ------------------------------------------------------------------------------
-- ROW LEVEL SECURITY (RLS) POLICIES
-- A user can only read and write their own rows.
-- The service role bypasses RLS on backend.
-- ------------------------------------------------------------------------------

-- Enable RLS on all 10 tables
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trust_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.paypal_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;

-- 1. tasks policies
CREATE POLICY "tasks_user_isolation_select" ON public.tasks FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "tasks_user_isolation_insert" ON public.tasks FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "tasks_user_isolation_update" ON public.tasks FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "tasks_user_isolation_delete" ON public.tasks FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- 2. task_policies policies
CREATE POLICY "task_policies_user_isolation_select" ON public.task_policies FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "task_policies_user_isolation_insert" ON public.task_policies FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "task_policies_user_isolation_update" ON public.task_policies FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "task_policies_user_isolation_delete" ON public.task_policies FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- 3. agents policies
CREATE POLICY "agents_user_isolation_select" ON public.agents FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "agents_user_isolation_insert" ON public.agents FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "agents_user_isolation_update" ON public.agents FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "agents_user_isolation_delete" ON public.agents FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- 4. agent_runs policies
CREATE POLICY "agent_runs_user_isolation_select" ON public.agent_runs FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "agent_runs_user_isolation_insert" ON public.agent_runs FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "agent_runs_user_isolation_update" ON public.agent_runs FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "agent_runs_user_isolation_delete" ON public.agent_runs FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- 5. quotes policies
CREATE POLICY "quotes_user_isolation_select" ON public.quotes FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "quotes_user_isolation_insert" ON public.quotes FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "quotes_user_isolation_update" ON public.quotes FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "quotes_user_isolation_delete" ON public.quotes FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- 6. transactions policies
CREATE POLICY "transactions_user_isolation_select" ON public.transactions FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "transactions_user_isolation_insert" ON public.transactions FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "transactions_user_isolation_update" ON public.transactions FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "transactions_user_isolation_delete" ON public.transactions FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- 7. trust_decisions policies
CREATE POLICY "trust_decisions_user_isolation_select" ON public.trust_decisions FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "trust_decisions_user_isolation_insert" ON public.trust_decisions FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "trust_decisions_user_isolation_update" ON public.trust_decisions FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "trust_decisions_user_isolation_delete" ON public.trust_decisions FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- 8. user_approvals policies
CREATE POLICY "user_approvals_user_isolation_select" ON public.user_approvals FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "user_approvals_user_isolation_insert" ON public.user_approvals FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "user_approvals_user_isolation_update" ON public.user_approvals FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "user_approvals_user_isolation_delete" ON public.user_approvals FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- 9. paypal_orders policies
CREATE POLICY "paypal_orders_user_isolation_select" ON public.paypal_orders FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "paypal_orders_user_isolation_insert" ON public.paypal_orders FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "paypal_orders_user_isolation_update" ON public.paypal_orders FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "paypal_orders_user_isolation_delete" ON public.paypal_orders FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- 10. audit_events policies (APPEND-ONLY: SELECT and INSERT only, NO UPDATE/DELETE)
CREATE POLICY "audit_events_user_isolation_select" ON public.audit_events FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "audit_events_user_isolation_insert" ON public.audit_events FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);

