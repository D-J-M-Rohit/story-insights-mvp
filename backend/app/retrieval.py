from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import uuid
from pathlib import Path

import numpy as np

from .config import settings
from .embeddings import content_sha256, deserialize_f32, embed_texts
from .logging_config import log_event
from .metrics import record_faiss_search_latency, record_retrieval_fallback, record_retrieval_latency

RETRIEVAL_FALLBACK_DISABLED = "disabled"
RETRIEVAL_NO_QUERY = "no_query"
RETRIEVAL_NO_RESULTS = "no_results"
RETRIEVAL_INDEX_MISSING = "index_missing"
RETRIEVAL_FAISS_ERROR = "faiss_error"
RETRIEVAL_EMBEDDING_ERROR = "embedding_error"
RETRIEVAL_STORE_ERROR = "store_error"
RETRIEVAL_CONFIG_ERROR = "config_error"
RETRIEVAL_UNKNOWN_ERROR = "unknown_error"
from .store import (
    create_faiss_index_metadata,
    get_active_faiss_index,
    list_fragment_embeddings_for_index,
    set_active_faiss_index,
)

_FAISS_CACHE = {}


def _matches_filters(row: dict, filters: dict | None) -> bool:
    filters = filters or {}
    if filters.get("scenario") and row.get("scenario") != filters.get("scenario"):
        return False
    if filters.get("scenario_pack_id") and row.get("scenario_pack_id") != filters.get("scenario_pack_id"):
        return False
    if filters.get("fragment_type") and row.get("fragment_type") != filters.get("fragment_type"):
        return False
    if filters.get("locale") and row.get("locale") != filters.get("locale"):
        return False
    if "active" in filters and bool(row.get("active")) != bool(filters.get("active")):
        return False
    tag_filters = filters.get("tags") or []
    if tag_filters:
        tags = set(row.get("tags_json") or [])
        if not set(tag_filters).issubset(tags):
            return False
    return True


def rerank_filtered_results(candidates: list[dict], required_filters: dict | None = None, final_k: int = 10) -> list[dict]:
    out = []
    for c in candidates:
        if not _matches_filters(c, required_filters):
            continue
        tags = set(c.get("tags_json") or [])
        required_tags = set((required_filters or {}).get("tags") or [])
        tag_overlap = (len(tags & required_tags) / len(required_tags)) if required_tags else 0.0
        freshness = 0.5
        final = 0.75 * float(c.get("vector_score", 0.0)) + 0.15 * tag_overlap + 0.10 * freshness
        out.append(
            {
                "fragment_id": c.get("id"),
                "fragment_key": c.get("fragment_key"),
                "content_text": c.get("content_text"),
                "vector_score": float(c.get("vector_score", 0.0)),
                "final_score": round(final, 6),
                "metadata": {
                    "scenario": c.get("scenario"),
                    "scenario_pack_id": c.get("scenario_pack_id"),
                    "fragment_type": c.get("fragment_type"),
                    "tags": c.get("tags_json") or [],
                },
            }
        )
    out.sort(key=lambda x: x["final_score"], reverse=True)
    return out[:final_k]


def exact_search(query_text: str, filters: dict | None = None, k: int = 10) -> list[dict]:
    rows = list_fragment_embeddings_for_index(filters=filters or {"active": True})
    if not rows:
        return []
    vec = embed_texts([query_text])
    if vec.size == 0:
        return []
    q = vec[0]
    scored = []
    for row in rows:
        try:
            v = deserialize_f32(row["embedding_f32"], int(row["embedding_dim"]))
            score = float(np.dot(q, v))
        except Exception:
            score = -1.0
        r = dict(row)
        r["vector_score"] = score
        scored.append(r)
    scored.sort(key=lambda x: x.get("vector_score", -1.0), reverse=True)
    return rerank_filtered_results(scored[: max(int(settings.RETRIEVAL_OVERFETCH_K), k * 5)], required_filters=filters, final_k=k)


def _faiss_index_paths(index_name: str):
    base = Path(settings.FAISS_INDEX_DIR)
    current = base / "current" / index_name / "index.faiss"
    return base, current


def build_faiss_index(index_name: str = "default", filters: dict | None = None) -> dict:
    rows = list_fragment_embeddings_for_index(filters=filters or {"active": True})
    if not rows:
        return {"status": "no_documents", "document_count": 0}
    import faiss

    dim = int(rows[0]["embedding_dim"])
    ids = []
    vectors = np.zeros((len(rows), dim), dtype=np.float32)
    for i, row in enumerate(rows):
        vectors[i] = deserialize_f32(row["embedding_f32"], dim)
        ids.append(i + 1)
    base_index = faiss.IndexHNSWFlat(dim, int(settings.FAISS_HNSW_M), faiss.METRIC_INNER_PRODUCT)
    base_index.hnsw.efConstruction = int(settings.FAISS_EF_CONSTRUCTION)
    base_index.hnsw.efSearch = int(settings.FAISS_EF_SEARCH)
    index = faiss.IndexIDMap2(base_index)
    index.add_with_ids(vectors, np.asarray(ids, dtype=np.int64))

    build_id = uuid.uuid4().hex
    base = Path(settings.FAISS_INDEX_DIR)
    shadow_dir = base / "build" / index_name / build_id
    shadow_dir.mkdir(parents=True, exist_ok=True)
    shadow_file = shadow_dir / "index.faiss"
    faiss.write_index(index, str(shadow_file))
    file_sha = "sha256:" + hashlib.sha256(shadow_file.read_bytes()).hexdigest()
    current_dir = base / "current" / index_name
    current_dir.mkdir(parents=True, exist_ok=True)
    current_file = current_dir / "index.faiss"
    tmp_file = current_dir / "index.faiss.tmp"
    shutil.copy2(shadow_file, tmp_file)
    os.replace(tmp_file, current_file)

    metadata = create_faiss_index_metadata(
        {
            "index_name": index_name,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dim": dim,
            "metric": "inner_product",
            "index_type": "hnsw",
            "hnsw_m": int(settings.FAISS_HNSW_M),
            "ef_construction": int(settings.FAISS_EF_CONSTRUCTION),
            "ef_search_default": int(settings.FAISS_EF_SEARCH),
            "document_count": len(rows),
            "index_sha256": file_sha,
            "local_path": str(current_file),
            "archived_blob_id": None,
            "source_snapshot_json": {
                "filters": filters or {},
                "build_id": build_id,
                "fragment_ids": [r.get("id") for r in rows],
            },
            "active": False,
            "built_at": None,
        }
    )
    metadata = set_active_faiss_index(index_name, metadata["id"]) or metadata
    _FAISS_CACHE[index_name] = {"index": index, "ids": ids, "meta": metadata}
    return metadata


def load_active_faiss_index(index_name: str = "default"):
    if index_name in _FAISS_CACHE:
        return _FAISS_CACHE[index_name]["index"], _FAISS_CACHE[index_name]["meta"]
    metadata = get_active_faiss_index(index_name=index_name)
    if not metadata or not metadata.get("local_path"):
        return None, metadata
    import faiss

    idx = faiss.read_index(str(metadata["local_path"]))
    _FAISS_CACHE[index_name] = {"index": idx, "meta": metadata}
    return idx, metadata


def faiss_search(query_text: str, filters: dict | None = None, k: int = 10) -> tuple[list[dict], str | None]:
    """Returns (results, index_missing_reason). Second value is set when FAISS index was unavailable and exact search was used."""
    started = time.perf_counter()
    index, metadata = load_active_faiss_index(settings.FAISS_INDEX_NAME)
    if index is None:
        return exact_search(query_text, filters=filters, k=k), RETRIEVAL_INDEX_MISSING
    rows = list_fragment_embeddings_for_index(filters={"active": True})
    row_by_ordinal = {i + 1: r for i, r in enumerate(rows)}
    query = embed_texts([query_text])
    fetch_k = max(int(settings.RETRIEVAL_OVERFETCH_K), k * 5)
    scores, ids = index.search(query.astype(np.float32), fetch_k)
    candidates = []
    for score, row_id in zip(scores[0], ids[0]):
        if int(row_id) <= 0:
            continue
        row = row_by_ordinal.get(int(row_id))
        if not row:
            continue
        item = dict(row)
        item["vector_score"] = float(score)
        candidates.append(item)
    results = rerank_filtered_results(candidates, required_filters=filters, final_k=k)
    if len(results) < k and fetch_k < 500:
        scores, ids = index.search(query.astype(np.float32), fetch_k * 2)
        candidates = []
        for score, row_id in zip(scores[0], ids[0]):
            row = row_by_ordinal.get(int(row_id))
            if row:
                item = dict(row)
                item["vector_score"] = float(score)
                candidates.append(item)
        results = rerank_filtered_results(candidates, required_filters=filters, final_k=k)
    elapsed = time.perf_counter() - started
    record_faiss_search_latency(settings.FAISS_INDEX_NAME, k, elapsed)
    record_retrieval_latency("faiss_hnsw", (filters or {}).get("scenario_pack_id", "any"), elapsed)
    return results, None


def retrieve_context_with_diagnostics(
    query_text: str, filters: dict | None = None, k: int | None = None
) -> dict:
    started = time.perf_counter()
    pack_label = (filters or {}).get("scenario_pack_id", "any")
    backend_cfg = (settings.RETRIEVAL_BACKEND or "none").lower()

    def _finish(items: list, backend: str, fallback_used: bool, reason: str) -> dict:
        dur_ms = round((time.perf_counter() - started) * 1000, 3)
        if fallback_used and reason:
            record_retrieval_fallback(backend, reason)
            log_event("retrieval_fallback", backend=backend, reason=reason)
        return {
            "items": items,
            "backend": backend,
            "fallback_used": fallback_used,
            "fallback_reason": reason,
            "duration_ms": dur_ms,
        }

    if not settings.RETRIEVAL_ENABLED or backend_cfg == "none":
        return _finish([], backend_cfg or "none", True, RETRIEVAL_FALLBACK_DISABLED)

    k = int(k or settings.RETRIEVAL_TOP_K or 10)
    qstrip = (query_text or "").strip()
    if not qstrip:
        return _finish([], backend_cfg, True, RETRIEVAL_NO_QUERY)

    if backend_cfg not in ("exact", "faiss_hnsw"):
        return _finish([], backend_cfg, True, RETRIEVAL_CONFIG_ERROR)

    result: list[dict] = []
    degraded: str | None = None
    try:
        if backend_cfg == "exact":
            result = exact_search(qstrip, filters=filters, k=k)
            record_retrieval_latency("exact", pack_label, time.perf_counter() - started)
        else:
            try:
                result, degraded = faiss_search(qstrip, filters=filters, k=k)
            except Exception as exc:
                log_event("retrieval_failed", backend="faiss_hnsw", error_type=type(exc).__name__)
                try:
                    result = exact_search(qstrip, filters=filters, k=k)
                    degraded = RETRIEVAL_FAISS_ERROR
                except Exception:
                    return _finish([], "faiss_hnsw", True, RETRIEVAL_FAISS_ERROR)
                record_retrieval_latency("exact", pack_label, time.perf_counter() - started)
            else:
                if degraded:
                    record_retrieval_latency("exact", pack_label, time.perf_counter() - started)
                else:
                    record_retrieval_latency("faiss_hnsw", pack_label, time.perf_counter() - started)
    except Exception as exc:
        log_event("retrieval_failed", backend=backend_cfg, error_type=type(exc).__name__)
        et = type(exc).__name__.lower()
        if "embedding" in et or "encode" in et or "torch" in et:
            reason = RETRIEVAL_EMBEDDING_ERROR
        elif "operational" in et or "sql" in et or "database" in et:
            reason = RETRIEVAL_STORE_ERROR
        else:
            reason = RETRIEVAL_UNKNOWN_ERROR
        return _finish([], backend_cfg, True, reason)

    if not result:
        return _finish(result, backend_cfg, True, degraded or RETRIEVAL_NO_RESULTS)
    if degraded:
        return _finish(result, backend_cfg, True, degraded)
    return _finish(result, backend_cfg, False, "")


def retrieve_context(query_text: str, filters: dict | None = None, k: int | None = None) -> list[dict]:
    return retrieve_context_with_diagnostics(query_text, filters=filters, k=k)["items"]
