from __future__ import annotations
import io
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import boto3
from botocore.config import Config
from PIL import Image

from core.config import get_settings

settings = get_settings()


class StorageBackend(ABC):
    @abstractmethod
    def save(self, content: bytes, filename: str, folder: str = "") -> str:
        """Save content and return the storage path."""
        pass

    @abstractmethod
    def load(self, path: str) -> bytes:
        """Load content from storage."""
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete content from storage."""
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if path exists."""
        pass

    def save_image(self, image: Image.Image, filename: str, folder: str = "") -> str:
        """Save PIL Image to storage."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return self.save(buffer.getvalue(), filename, folder)


class LocalStorage(StorageBackend):
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _full_path(self, path: str) -> Path:
        return self.base_path / path

    def save(self, content: bytes, filename: str, folder: str = "") -> str:
        date_folder = datetime.utcnow().strftime("%Y/%m/%d")
        unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        rel_path = Path(folder) / date_folder / unique_name

        full_path = self._full_path(str(rel_path))
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)

        return str(rel_path)

    def load(self, path: str) -> bytes:
        return self._full_path(path).read_bytes()

    def delete(self, path: str) -> bool:
        try:
            self._full_path(path).unlink()
            return True
        except FileNotFoundError:
            return False

    def exists(self, path: str) -> bool:
        return self._full_path(path).exists()


class S3Storage(StorageBackend):
    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
    ):
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def save(self, content: bytes, filename: str, folder: str = "") -> str:
        date_folder = datetime.utcnow().strftime("%Y/%m/%d")
        unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        key = f"{folder}/{date_folder}/{unique_name}" if folder else f"{date_folder}/{unique_name}"
        key = key.lstrip("/")

        self.client.put_object(Bucket=self.bucket, Key=key, Body=content)
        return key

    def load(self, path: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=path)
        return response["Body"].read()

    def delete(self, path: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False

    def exists(self, path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=path)
            return True
        except Exception:
            return False


def get_storage() -> StorageBackend:
    """Get configured storage backend."""
    if settings.storage_type == "s3":
        return S3Storage(
            endpoint=settings.s3_endpoint,
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            bucket=settings.s3_bucket,
        )
    return LocalStorage(settings.storage_path)
