from __future__ import annotations

import os
from typing import BinaryIO

import boto3
from botocore.config import Config


_s3_client: S3Client | None = None


class S3Client:
    """S3/R2-compatible object storage client."""

    def __init__(
        self,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        bucket_name: str | None = None,
        region: str | None = None,
    ):
        self._bucket = bucket_name or os.getenv("S3_BUCKET_NAME", "kira-assets")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or os.getenv("S3_ENDPOINT_URL"),
            aws_access_key_id=access_key_id or os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=secret_access_key or os.getenv("S3_SECRET_ACCESS_KEY"),
            region_name=region or os.getenv("S3_REGION", "auto"),
            config=Config(signature_version="s3v4"),
        )

    def build_storage_key(
        self,
        org_id: str,
        project_id: str,
        asset_id: str,
        filename: str,
    ) -> str:
        return f"orgs/{org_id}/projects/{project_id}/assets/{asset_id}/{filename}"

    def build_source_storage_key(
        self,
        org_id: str,
        source_doc_id: str,
        filename: str,
    ) -> str:
        return f"orgs/{org_id}/sources/{source_doc_id}/{filename}"

    def generate_presigned_upload_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires_in: int = 3600,
    ) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    def generate_presigned_download_url(
        self,
        key: str,
        original_filename: str | None = None,
        expires_in: int = 3600,
    ) -> str:
        params: dict = {"Bucket": self._bucket, "Key": key}
        if original_filename:
            params["ResponseContentDisposition"] = (
                f'attachment; filename="{original_filename}"'
            )
        return self._client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )

    def upload_fileobj(
        self,
        fileobj: BinaryIO,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> None:
        self._client.upload_fileobj(
            fileobj,
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    def download_fileobj(self, key: str, fileobj: BinaryIO) -> None:
        self._client.download_fileobj(self._bucket, key, fileobj)

    def head_object(self, key: str) -> dict:
        return self._client.head_object(Bucket=self._bucket, Key=key)

    def delete_object(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def build_full_uri(self, key: str) -> str:
        """Build canonical s3://bucket/key URI."""
        return f"s3://{self._bucket}/{key}"

    def parse_storage_uri(self, uri: str) -> str:
        """Extract S3 key from storage_uri. Raises ValueError if format wrong."""
        prefix = f"s3://{self._bucket}/"
        if not uri.startswith(prefix):
            raise ValueError(f"Invalid storage URI: {uri}")
        return uri[len(prefix):]


def get_s3_client() -> S3Client:
    global _s3_client
    if _s3_client is None:
        _s3_client = S3Client()
    return _s3_client
