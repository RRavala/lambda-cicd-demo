CREATE TABLE IF NOT EXISTS s3_uploads (
    id                SERIAL PRIMARY KEY,
    s3_bucket         TEXT NOT NULL,
    s3_key            TEXT NOT NULL,
    file_size_bytes   BIGINT,
    etag              TEXT,
    content_type      TEXT,
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (s3_bucket, s3_key)
);
