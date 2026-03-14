"""Layer 3: Storage Integration Tests — MinIO/R2 upload/download/checksum."""
from __future__ import annotations

import io
import hashlib
import os
import pytest
from services.web_app.storage.s3 import S3Client

_STORAGE_TEST_URL = os.getenv("S3_TEST_ENDPOINT_URL")


@pytest.fixture
def s3_client():
    if not _STORAGE_TEST_URL:
        pytest.skip("S3_TEST_ENDPOINT_URL not set")
    return S3Client(
        endpoint_url=_STORAGE_TEST_URL,
        access_key_id=os.getenv("S3_TEST_ACCESS_KEY", "minioadmin"),
        secret_access_key=os.getenv("S3_TEST_SECRET_KEY", "minioadmin"),
        bucket_name="kira-test-assets",
        region="us-east-1",
    )


def test_upload_download_roundtrip(s3_client):
    """Upload -> head -> download -> verify content matches."""
    content = "테스트 문서 내용".encode("utf-8")
    key = "test/roundtrip/test.txt"

    s3_client.upload_fileobj(io.BytesIO(content), key, "text/plain")

    head = s3_client.head_object(key)
    assert head["ContentLength"] == len(content)

    buf = io.BytesIO()
    s3_client.download_fileobj(key, buf)
    assert buf.getvalue() == content

    s3_client.delete_object(key)


def test_presigned_url_generation(s3_client):
    """Presigned upload + download URLs are valid format."""
    key = "test/presigned/test.docx"
    upload_url = s3_client.generate_presigned_upload_url(key)
    assert "X-Amz-Signature" in upload_url or "Signature" in upload_url

    download_url = s3_client.generate_presigned_download_url(key, "test.docx")
    assert "X-Amz-Signature" in download_url or "Signature" in download_url


def test_checksum_verification(s3_client):
    """Upload file and verify ETag matches content hash."""
    content = b"checksum test data"
    expected_md5 = hashlib.md5(content).hexdigest()
    key = "test/checksum/verify.bin"

    s3_client.upload_fileobj(io.BytesIO(content), key)
    head = s3_client.head_object(key)
    etag = head.get("ETag", "").strip('"')

    assert etag == expected_md5

    s3_client.delete_object(key)
