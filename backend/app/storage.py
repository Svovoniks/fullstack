from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO

import boto3
from botocore.client import BaseClient
from botocore.exceptions import BotoCoreError, ClientError


class StorageError(Exception):
    pass


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    raise StorageError(f"Missing required environment variable: {name}")


@dataclass(frozen=True)
class StorageConfig:
    endpoint_url: str
    region_name: str
    access_key_id: str
    secret_access_key: str
    bucket_name: str


class ObjectStorage:
    def __init__(self, config: StorageConfig) -> None:
        self.config = config
        self.client = boto3.client(
            "s3",
            endpoint_url=config.endpoint_url,
            region_name=config.region_name,
            aws_access_key_id=config.access_key_id,
            aws_secret_access_key=config.secret_access_key,
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.config.bucket_name)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "")
            if code not in {"404", "NoSuchBucket"}:
                raise StorageError("Failed to access object storage bucket") from error

            create_kwargs: dict[str, object] = {"Bucket": self.config.bucket_name}
            if self.config.region_name != "us-east-1":
                create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self.config.region_name}

            try:
                self.client.create_bucket(**create_kwargs)
            except (BotoCoreError, ClientError) as create_error:
                raise StorageError("Failed to create object storage bucket") from create_error
        except (BotoCoreError, ClientError) as error:
            raise StorageError("Failed to access object storage bucket") from error

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self.client.upload_fileobj(
                Fileobj=BytesIO(data),
                Bucket=self.config.bucket_name,
                Key=key,
                ExtraArgs={"ContentType": content_type},
            )
        except (BotoCoreError, ClientError) as error:
            raise StorageError("Failed to upload object to storage") from error

    def download_object(self, key: str) -> tuple[bytes, str | None]:
        try:
            response = self.client.get_object(Bucket=self.config.bucket_name, Key=key)
            body = response["Body"].read()
            return body, response.get("ContentType")
        except (BotoCoreError, ClientError) as error:
            raise StorageError("Failed to download object from storage") from error


def get_storage_config() -> StorageConfig:
    return StorageConfig(
        endpoint_url=_require_env("S3_ENDPOINT_URL"),
        region_name=_require_env("S3_REGION"),
        access_key_id=_require_env("S3_ACCESS_KEY_ID"),
        secret_access_key=_require_env("S3_SECRET_ACCESS_KEY"),
        bucket_name=_require_env("S3_BUCKET_NAME"),
    )


@lru_cache
def get_storage() -> ObjectStorage:
    return ObjectStorage(get_storage_config())
