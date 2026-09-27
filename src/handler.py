"""
Learning example: an S3-triggered Lambda that writes basic object metadata
to a PostgreSQL table whenever a file is uploaded.

Flow:
    S3 ObjectCreated -> Lambda -> INSERT/UPDATE a row in `s3_uploads`

Environment variables:
    DB_SECRET_ARN   Secrets Manager secret ARN holding DB creds
                    (keys: host, port, dbname, username, password)
    DB_TABLE        target table name (default: s3_uploads)
"""
import json
import logging
import os
import urllib.parse
from datetime import datetime, timezone

import boto3
import psycopg2

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

s3_client = boto3.client("s3")
secrets_client = boto3.client("secretsmanager")

DB_TABLE = os.environ.get("DB_TABLE", "s3_uploads")
DB_SECRET_ARN = os.environ["DB_SECRET_ARN"]

_conn = None
_secret_cache = None


def _get_db_secret():
    global _secret_cache
    if _secret_cache is None:
        resp = secrets_client.get_secret_value(SecretId=DB_SECRET_ARN)
        _secret_cache = json.loads(resp["SecretString"])
    return _secret_cache


def _get_connection():
    global _conn
    if _conn is not None and _conn.closed == 0:
        return _conn

    secret = _get_db_secret()
    _conn = psycopg2.connect(
        host=secret["host"],
        port=secret.get("port", 5432),
        dbname=secret["dbname"],
        user=secret["username"],
        password=secret["password"],
        connect_timeout=5,
    )
    return _conn


def _extract_metadata(bucket: str, key: str) -> dict:
    head = s3_client.head_object(Bucket=bucket, Key=key)
    return {
        "s3_bucket": bucket,
        "s3_key": key,
        "file_size_bytes": head["ContentLength"],
        "etag": head["ETag"].strip('"'),
        "content_type": head.get("ContentType"),
        "uploaded_at": datetime.now(timezone.utc),
    }


UPSERT_SQL = """
    INSERT INTO {table} (s3_bucket, s3_key, file_size_bytes, etag, content_type, uploaded_at)
    VALUES (%(s3_bucket)s, %(s3_key)s, %(file_size_bytes)s, %(etag)s, %(content_type)s, %(uploaded_at)s)
    ON CONFLICT (s3_bucket, s3_key) DO UPDATE SET
        file_size_bytes = EXCLUDED.file_size_bytes,
        etag            = EXCLUDED.etag,
        content_type    = EXCLUDED.content_type,
        uploaded_at     = EXCLUDED.uploaded_at
""".format(table=DB_TABLE)


def handler(event, context):
    records = event.get("Records", [])
    processed, failed = 0, []

    conn = _get_connection()

    with conn.cursor() as cur:
        for record in records:
            try:
                bucket = record["s3"]["bucket"]["name"]
                key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])

                metadata = _extract_metadata(bucket, key)
                cur.execute(UPSERT_SQL, metadata)
                processed += 1
                logger.info("Upserted metadata for %s/%s", bucket, key)
            except Exception:
                logger.exception("Failed processing record: %s", record)
                failed.append(record)

        conn.commit()

    if failed:
        raise RuntimeError(f"{len(failed)} of {len(records)} records failed")

    return {"processed": processed}
