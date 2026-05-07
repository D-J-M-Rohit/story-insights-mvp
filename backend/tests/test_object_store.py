from datetime import datetime, timezone
import uuid

from app.object_store import build_object_key, delete_object, get_signed_download_url, put_bytes
from app.store import create_archived_blob, list_expired_archived_blobs, mark_archived_blob_deleted


def test_build_object_keys():
    dt = datetime(2026, 5, 7, tzinfo=timezone.utc)
    assert "traces/raw/2026/05/07/s1/t1.json.gz" == build_object_key("trace", "s1", "t1", dt)
    assert "prompts/archive/2026/05/07/s1/g1.json.gz" == build_object_key("prompt", "s1", "g1", dt)
    assert "reports/pdf/2026/05/07/s1/latest.pdf" == build_object_key("pdf", "s1", "latest", dt, extension="pdf")
    assert "faiss/indexes/default/b1/index.faiss" == build_object_key("faiss_snapshot", "default", "b1", dt)


def test_filesystem_put_and_delete():
    key = "tests/blob.bin"
    out = put_bytes("trace", key, b"hello", "application/octet-stream")
    assert out["size_bytes"] == 5
    delete_object(key)


def test_signed_url_filesystem():
    assert get_signed_download_url("x/y/z") is None


def test_archived_blob_metadata_roundtrip():
    blob_id = f"blob-test-{uuid.uuid4().hex[:8]}"
    row = create_archived_blob(
        {
            "id": blob_id,
            "blob_type": "trace",
            "storage_backend": "filesystem",
            "bucket": None,
            "object_key": "tests/blob-1.json.gz",
            "content_type": "application/json",
            "content_encoding": "gzip",
            "size_bytes": 10,
            "sha256": "sha256:abc",
            "kms_key_id": None,
            "session_id": "s1",
            "report_id": None,
            "generation_trace_id": None,
            "created_at": datetime.now(timezone.utc),
            "retention_until": datetime.now(timezone.utc),
            "deleted_at": None,
            "metadata_json": {},
        }
    )
    assert row["id"] == blob_id
    expired = list_expired_archived_blobs(limit=10)
    assert any(r["id"] == blob_id for r in expired)
    marked = mark_archived_blob_deleted(blob_id)
    assert marked["deleted_at"] is not None
