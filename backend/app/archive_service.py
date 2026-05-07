from __future__ import annotations

import gzip
import json
import uuid
from datetime import datetime, timedelta, timezone

from .config import settings
from .logging_config import redact_sensitive
from .object_store import build_object_key, delete_object, put_bytes
from .store import create_archived_blob, list_expired_archived_blobs, mark_archived_blob_deleted


def _retention_days(blob_type: str) -> int:
    if blob_type == "trace":
        return int(settings.ARCHIVE_TRACE_RETENTION_DAYS or 30)
    if blob_type == "prompt":
        return int(settings.ARCHIVE_PROMPT_RETENTION_DAYS or 30)
    if blob_type == "pdf":
        return int(settings.ARCHIVE_PDF_RETENTION_DAYS or 7)
    if blob_type == "faiss_snapshot":
        return int(settings.ARCHIVE_FAISS_SNAPSHOT_RETENTION_DAYS or 14)
    return 30


def _store_blob(blob_type: str, session_id: str | None, object_id: str, data: bytes, content_type: str, content_encoding=None, metadata=None):
    now = datetime.now(timezone.utc)
    object_key = build_object_key(blob_type, session_id, object_id, now, extension=None)
    put = put_bytes(blob_type, object_key, data, content_type=content_type, content_encoding=content_encoding, metadata=metadata or {})
    return create_archived_blob(
        {
            "id": str(uuid.uuid4()),
            "blob_type": blob_type,
            "storage_backend": put["storage_backend"],
            "bucket": put.get("bucket"),
            "object_key": put["object_key"],
            "content_type": put.get("content_type"),
            "content_encoding": put.get("content_encoding"),
            "size_bytes": put["size_bytes"],
            "sha256": put["sha256"],
            "kms_key_id": None,
            "session_id": session_id,
            "report_id": (metadata or {}).get("report_id"),
            "generation_trace_id": (metadata or {}).get("generation_trace_id"),
            "created_at": now,
            "retention_until": now + timedelta(days=_retention_days(blob_type)),
            "deleted_at": None,
            "metadata_json": metadata or {},
        }
    )


def archive_generation_trace(trace: dict) -> dict | None:
    if not settings.OBJECT_ARCHIVE_ENABLED or not settings.ARCHIVE_RAW_TRACES_ENABLED:
        return None
    safe = redact_sensitive(trace or {})
    body = gzip.compress(json.dumps(safe, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    return _store_blob(
        "trace",
        session_id=(trace or {}).get("session_id"),
        object_id=(trace or {}).get("id") or str(uuid.uuid4()),
        data=body,
        content_type="application/json",
        content_encoding="gzip",
        metadata={"generation_trace_id": (trace or {}).get("id")},
    )


def archive_prompt_payload(prompt_payload: dict) -> dict | None:
    if not settings.OBJECT_ARCHIVE_ENABLED or not settings.ARCHIVE_PROMPTS_ENABLED:
        return None
    safe = redact_sensitive(prompt_payload or {})
    body = gzip.compress(json.dumps(safe, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    return _store_blob(
        "prompt",
        session_id=(prompt_payload or {}).get("session_id"),
        object_id=(prompt_payload or {}).get("generation_trace_id") or str(uuid.uuid4()),
        data=body,
        content_type="application/json",
        content_encoding="gzip",
        metadata={"generation_trace_id": (prompt_payload or {}).get("generation_trace_id")},
    )


def archive_pdf_bytes(session_id: str, report_id: str, pdf_bytes: bytes, report_version: str = "latest") -> dict | None:
    if not settings.OBJECT_ARCHIVE_ENABLED or not settings.ARCHIVE_PDFS_ENABLED:
        return None
    return _store_blob(
        "pdf",
        session_id=session_id,
        object_id=report_version,
        data=pdf_bytes,
        content_type="application/pdf",
        content_encoding=None,
        metadata={"report_id": report_id},
    )


def archive_faiss_snapshot(index_path: str, metadata: dict) -> dict | None:
    if not settings.OBJECT_ARCHIVE_ENABLED:
        return None
    data = open(index_path, "rb").read()  # noqa: SIM115
    return _store_blob(
        "faiss_snapshot",
        session_id=(metadata or {}).get("index_name"),
        object_id=(metadata or {}).get("id") or str(uuid.uuid4()),
        data=data,
        content_type="application/octet-stream",
        metadata={"index_name": (metadata or {}).get("index_name")},
    )


def purge_expired_archives(limit: int = 100) -> dict:
    expired = list_expired_archived_blobs(limit=limit)
    deleted = 0
    for row in expired:
        try:
            delete_object(row["object_key"])
            mark_archived_blob_deleted(row["id"])
            deleted += 1
        except Exception:
            continue
    return {"expired_seen": len(expired), "deleted": deleted}
