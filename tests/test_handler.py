import os
import sys
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


@mock_aws
def test_extract_metadata_reads_head_object():
    import handler

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="demo-bucket")
    s3.put_object(
        Bucket="demo-bucket",
        Key="hello.txt",
        Body=b"hello world",
        ContentType="text/plain",
    )

    handler.s3_client = s3

    result = handler._extract_metadata("demo-bucket", "hello.txt")

    assert result["s3_bucket"] == "demo-bucket"
    assert result["s3_key"] == "hello.txt"
    assert result["content_type"] == "text/plain"
    assert result["file_size_bytes"] == len(b"hello world")


def test_handler_upserts_each_record_and_commits():
    import handler

    fake_cursor = MagicMock()
    fake_cursor.__enter__.return_value = fake_cursor
    fake_cursor.__exit__.return_value = False

    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor
    fake_conn.closed = 0

    event = {
        "Records": [
            {"s3": {"bucket": {"name": "demo-bucket"}, "object": {"key": "hello.txt"}}}
        ]
    }

    with patch.object(handler, "_get_connection", return_value=fake_conn), \
         patch.object(handler, "_extract_metadata", return_value={
             "s3_bucket": "demo-bucket", "s3_key": "hello.txt",
             "file_size_bytes": 11, "etag": "x", "content_type": "text/plain",
             "uploaded_at": "2026-01-01T00:00:00Z",
         }):
        result = handler.handler(event, context=None)

    assert result == {"processed": 1}
    fake_cursor.execute.assert_called_once()
    fake_conn.commit.assert_called_once()


def test_handler_raises_when_a_record_fails():
    import handler

    fake_cursor = MagicMock()
    fake_cursor.__enter__.return_value = fake_cursor
    fake_cursor.__exit__.return_value = False

    fake_conn = MagicMock()
    fake_conn.cursor.return_value = fake_cursor
    fake_conn.closed = 0

    event = {
        "Records": [
            {"s3": {"bucket": {"name": "demo-bucket"}, "object": {"key": "bad.txt"}}}
        ]
    }

    with patch.object(handler, "_get_connection", return_value=fake_conn), \
         patch.object(handler, "_extract_metadata", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            handler.handler(event, context=None)
