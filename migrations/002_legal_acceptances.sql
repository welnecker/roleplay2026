CREATE TABLE IF NOT EXISTS legal_acceptances (
    user_id text PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    terms_version text NOT NULL,
    privacy_version text NOT NULL,
    accepted_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
