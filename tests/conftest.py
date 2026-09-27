import os

os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault(
    "DB_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:123456789012:secret:test"
)
