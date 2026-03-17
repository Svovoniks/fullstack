CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL
);

INSERT INTO users (id, username, password_hash, created_at)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'admin',
    '100000$OWWBT0KnAkj07QqlYNSecw==$1D89gEkPsGX5q3a69TtpudsQ2QrF5cQPW21LMcYVfWw=',
    NOW()
)
ON CONFLICT (username) DO NOTHING;

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    filename TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    source_object_key TEXT,
    result_object_key TEXT,
    content_type TEXT,
    result_content_type TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL
);
