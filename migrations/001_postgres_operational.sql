-- Roleplay2026 operational PostgreSQL schema.
-- ROTEIROS intentionally remains in Google Sheets.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    user_id text PRIMARY KEY,
    email text NOT NULL,
    display_name text NOT NULL,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_email_normalized_unique UNIQUE (email)
);

CREATE TABLE IF NOT EXISTS user_credentials (
    credential_id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    password_hash text NOT NULL,
    status text NOT NULL DEFAULT 'active',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_credential_per_user
    ON user_credentials(user_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS user_entitlements (
    entitlement_id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    package_id text NOT NULL,
    product_id text NOT NULL,
    status text NOT NULL DEFAULT 'active',
    source text NOT NULL,
    payment_id text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_entitlement_per_package
    ON user_entitlements(user_id, package_id) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS payment_orders (
    payment_order_id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    package_id text NOT NULL,
    product_id text NOT NULL,
    amount_cents integer NOT NULL CHECK (amount_cents > 0),
    currency text NOT NULL,
    payer_email_normalized text NOT NULL,
    payment_mode text NOT NULL,
    provider text NOT NULL,
    provider_order_id text,
    external_reference text NOT NULL UNIQUE,
    idempotency_key text NOT NULL UNIQUE,
    status text NOT NULL,
    status_detail text NOT NULL DEFAULT '',
    qr_code text NOT NULL DEFAULT '',
    ticket_url text NOT NULL DEFAULT '',
    validation_status text NOT NULL DEFAULT 'pending',
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS payment_provider_order_unique
    ON payment_orders(provider, provider_order_id)
    WHERE provider_order_id IS NOT NULL AND provider_order_id <> '';

CREATE TABLE IF NOT EXISTS payment_events (
    payment_event_id text PRIMARY KEY,
    payment_order_id text NOT NULL REFERENCES payment_orders(payment_order_id) ON DELETE CASCADE,
    provider_order_id text NOT NULL DEFAULT '',
    event_type text NOT NULL,
    status text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS webhook_events (
    webhook_event_id text PRIMARY KEY,
    provider_event_id text NOT NULL,
    provider_order_id text NOT NULL DEFAULT '',
    event_type text NOT NULL,
    signature_valid boolean NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS webhook_provider_event_unique
    ON webhook_events(provider_event_id) WHERE provider_event_id <> '';

CREATE TABLE IF NOT EXISTS story_credits (
    credit_id text PRIMARY KEY,
    user_id text NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    package_id text NOT NULL,
    payment_id text NOT NULL,
    status text NOT NULL DEFAULT 'available',
    run_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    consumed_at timestamptz,
    revoked_at timestamptz,
    CONSTRAINT story_credit_payment_unique UNIQUE (package_id, payment_id)
);
CREATE INDEX IF NOT EXISTS story_credit_available_lookup
    ON story_credits(user_id, package_id, created_at)
    WHERE status = 'available';

CREATE TABLE IF NOT EXISTS story_runs (
    run_id text PRIMARY KEY,
    credit_id text NOT NULL DEFAULT '',
    user_id text NOT NULL REFERENCES users(user_id) ON DELETE RESTRICT,
    package_id text NOT NULL,
    script_version text NOT NULL,
    current_block_id text NOT NULL,
    current_beat_id text NOT NULL,
    status text NOT NULL DEFAULT 'active',
    ending_code text NOT NULL DEFAULT '',
    state_version integer NOT NULL DEFAULT 1 CHECK (state_version >= 1),
    permanent_memory_ids_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    started_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_run_per_user_package
    ON story_runs(user_id, package_id) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS story_runs_resume_lookup
    ON story_runs(user_id, package_id, updated_at DESC);

ALTER TABLE story_credits
    DROP CONSTRAINT IF EXISTS story_credits_run_id_fkey;
ALTER TABLE story_credits
    ADD CONSTRAINT story_credits_run_id_fkey
    FOREIGN KEY (run_id) REFERENCES story_runs(run_id) ON DELETE SET NULL
    DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE IF NOT EXISTS runtime_sessions (
    session_id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES story_runs(run_id) ON DELETE CASCADE,
    user_id text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    package_id text NOT NULL,
    instance_id text NOT NULL,
    status text NOT NULL DEFAULT 'active',
    started_at timestamptz NOT NULL DEFAULT now(),
    last_seen_at timestamptz NOT NULL DEFAULT now(),
    ended_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_session_per_instance
    ON runtime_sessions(run_id, user_id, package_id, instance_id)
    WHERE status = 'active';

CREATE TABLE IF NOT EXISTS interactions (
    interaction_id text PRIMARY KEY,
    session_id text NOT NULL REFERENCES runtime_sessions(session_id) ON DELETE CASCADE,
    run_id text NOT NULL REFERENCES story_runs(run_id) ON DELETE CASCADE,
    user_id text NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    package_id text NOT NULL,
    sequence integer NOT NULL CHECK (sequence > 0),
    role text NOT NULL,
    speaker_id text NOT NULL DEFAULT '',
    content text NOT NULL,
    block_id text NOT NULL DEFAULT '',
    beat_id text NOT NULL DEFAULT '',
    user_intent text NOT NULL DEFAULT '',
    beat_consumed boolean NOT NULL DEFAULT false,
    model text NOT NULL DEFAULT '',
    input_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    latency_ms integer NOT NULL DEFAULT 0,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT interaction_sequence_role_unique UNIQUE (run_id, sequence, role)
);
CREATE INDEX IF NOT EXISTS interactions_recovery
    ON interactions(run_id, sequence DESC);

CREATE TABLE IF NOT EXISTS run_memories (
    run_memory_id text PRIMARY KEY,
    run_id text NOT NULL REFERENCES story_runs(run_id) ON DELETE CASCADE,
    memory_id text NOT NULL,
    source_beat_id text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT run_memory_unique UNIQUE (run_id, memory_id)
);
