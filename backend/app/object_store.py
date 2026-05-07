from __future__ import annotations

import gzip
import hashlib
import os
from datetime import datetime
from pathlib import Path

from .config import settings
from .logging_config import log_event
from .metrics import record_archive_size, record_object_store_put


def build_object_key(blob_type: str, session_id: str | None, object_id: str, created_at: datetime, extension: str | None = None) -> str:
    d = created_at
    if blob_type == "trace":
        return f"traces/raw/{d:%Y/%m/%d}/{session_id or 'na'}/{object_id}.json.gz"
    if blob_type == "prompt":
        return f"prompts/archive/{d:%Y/%m/%d}/{session_id or 'na'}/{object_id}.json.gz"
    if blob_type == "pdf":
        ext = extension or "pdf"
        return f"reports/pdf/{d:%Y/%m/%d}/{session_id or 'na'}/{object_id}.{ext}"
    if blob_type == "faiss_snapshot":
        return f"faiss/indexes/{session_id or 'default'}/{object_id}/index.faiss"
    return f"misc/{d:%Y/%m/%d}/{object_id}"


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _filesystem_put(object_key: str, data: bytes):
    root = Path(settings.OBJECT_STORAGE_FILESYSTEM_ROOT)
    target = root / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def put_bytes(
    blob_type: str,
    object_key: str,
    data: bytes,
    content_type: str,
    content_encoding: str | None = None,
    metadata: dict | None = None,
) -> dict:
    started = datetime.now()
    backend = (settings.OBJECT_STORAGE_BACKEND or "filesystem").lower()
    metadata = metadata or {}
    if backend == "filesystem":
        _filesystem_put(object_key, data)
        elapsed = (datetime.now() - started).total_seconds()
    else:
        import boto3

        client = boto3.client(
            "s3",
            endpoint_url=settings.OBJECT_STORAGE_ENDPOINT or None,
            region_name=settings.OBJECT_STORAGE_REGION or None,
            aws_access_key_id=settings.OBJECT_STORAGE_ACCESS_KEY or None,
            aws_secret_access_key=settings.OBJECT_STORAGE_SECRET_KEY or None,
        )
        extra = {"ContentType": content_type}
        if content_encoding:
            extra["ContentEncoding"] = content_encoding
        if metadata:
            extra["Metadata"] = {k: str(v)[:128] for k, v in metadata.items()}
        client.put_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=object_key, Body=data, **extra)
        elapsed = (datetime.now() - started).total_seconds()
    result = {
        "storage_backend": backend,
        "bucket": (settings.OBJECT_STORAGE_BUCKET if backend in {"s3", "minio"} else None),
        "object_key": object_key,
        "size_bytes": len(data),
        "sha256": _sha256_bytes(data),
        "content_type": content_type,
        "content_encoding": content_encoding,
    }
    record_object_store_put(backend, blob_type, elapsed)
    record_archive_size(backend, blob_type, len(data))
    return result


def get_signed_download_url(object_key: str, expires_sec: int | None = None) -> str | None:
    backend = (settings.OBJECT_STORAGE_BACKEND or "filesystem").lower()
    ttl = int(expires_sec or settings.OBJECT_STORAGE_SIGNED_URL_TTL_SEC or 300)
    if backend == "filesystem":
        return None
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=settings.OBJECT_STORAGE_ENDPOINT or None,
        region_name=settings.OBJECT_STORAGE_REGION or None,
        aws_access_key_id=settings.OBJECT_STORAGE_ACCESS_KEY or None,
        aws_secret_access_key=settings.OBJECT_STORAGE_SECRET_KEY or None,
    )
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.OBJECT_STORAGE_BUCKET, "Key": object_key},
        ExpiresIn=ttl,
    )


def delete_object(object_key: str) -> None:
    backend = (settings.OBJECT_STORAGE_BACKEND or "filesystem").lower()
    if backend == "filesystem":
        path = Path(settings.OBJECT_STORAGE_FILESYSTEM_ROOT) / object_key
        if path.exists():
            path.unlink()
        return
    import boto3

    client = boto3.client(
        "s3",
        endpoint_url=settings.OBJECT_STORAGE_ENDPOINT or None,
        region_name=settings.OBJECT_STORAGE_REGION or None,
        aws_access_key_id=settings.OBJECT_STORAGE_ACCESS_KEY or None,
        aws_secret_access_key=settings.OBJECT_STORAGE_SECRET_KEY or None,
    )
    client.delete_object(Bucket=settings.OBJECT_STORAGE_BUCKET, Key=object_key)


def gzip_json_bytes(payload: dict) -> bytes:
    raw = str(payload).encode("utf-8")
    return gzip.compress(raw, compresslevel=6)
