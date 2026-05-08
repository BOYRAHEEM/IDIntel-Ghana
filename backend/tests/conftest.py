"""Pytest configuration and shared fixtures.

Test RSA keys are generated at session start into a temp directory
so that no PEM files need to be committed to version control.
"""
import os
import tempfile
from pathlib import Path

import pytest


def _generate_test_rsa_keys(tmp_dir: str) -> tuple[str, str]:
    """Generate a temporary RSA-4096 key pair and return (private_path, public_path)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_path = os.path.join(tmp_dir, "test_private_key.pem")
    public_path = os.path.join(tmp_dir, "test_public_key.pem")

    with open(private_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    with open(public_path, "wb") as f:
        f.write(private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ))

    return private_path, public_path


# Generate test keys before settings are imported
_tmp_key_dir = tempfile.mkdtemp(prefix="idintel_test_keys_")
_private_key_path, _public_key_path = _generate_test_rsa_keys(_tmp_key_dir)

# Set all required environment variables
os.environ["ENVIRONMENT"] = "development"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/idintel_test"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["SECRET_KEY"] = "a" * 64
os.environ["JWT_PRIVATE_KEY_PATH"] = _private_key_path
os.environ["JWT_PUBLIC_KEY_PATH"] = _public_key_path
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_KMS_KEY_ID"] = "test-kms-key"
os.environ["AWS_KMS_AUDIT_KEY_ID"] = "test-audit-kms-key"
os.environ["NIA_API_BASE_URL"] = "http://mock-nia:8080"
os.environ["NIA_API_CLIENT_CERT_PATH"] = "/dev/null"
os.environ["NIA_API_CLIENT_KEY_PATH"] = "/dev/null"
os.environ["NIA_API_CA_CERT_PATH"] = "/dev/null"
os.environ["ANTHROPIC_API_KEY"] = "test-anthropic-key"
os.environ["ELASTICSEARCH_URL"] = "http://localhost:9200"
os.environ["ELASTICSEARCH_API_KEY"] = "test"
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["NEO4J_USER"] = "neo4j"
os.environ["NEO4J_PASSWORD"] = "test"
os.environ["CELERY_BROKER_URL"] = "memory://"
os.environ["CELERY_RESULT_BACKEND"] = "cache+memory://"
os.environ["AWS_S3_BUCKET_REPORTS"] = "test-reports-bucket"
os.environ["AWS_S3_BUCKET_AUDIT"] = "test-audit-bucket"
os.environ["GIS_API_BASE_URL"] = "http://mock-gis:8080"
os.environ["GIS_API_API_KEY"] = "test-gis-key"
os.environ["MTLS_REQUIRED"] = "false"
os.environ["IP_ALLOWLIST_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["PROMETHEUS_ENABLED"] = "false"
