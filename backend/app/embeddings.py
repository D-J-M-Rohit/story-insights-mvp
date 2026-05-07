from __future__ import annotations

import hashlib
from typing import Any

import numpy as np

from .config import settings
from .logging_config import log_event
from .metrics import record_embedding_throughput
from .store import list_fragment_embeddings_for_index, list_scenario_packs, upsert_fragment_embedding

_MODEL = None


def content_sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def get_embedding_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(
            settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE or "cpu",
            cache_folder=settings.EMBEDDING_CACHE_DIR or None,
            revision=settings.EMBEDDING_REVISION or None,
        )
    return _MODEL


def embed_texts(texts: list[str], batch_size: int | None = None) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    model = get_embedding_model()
    arr = model.encode(
        texts,
        batch_size=batch_size or int(settings.EMBEDDING_BATCH_SIZE or 64),
        convert_to_numpy=True,
        normalize_embeddings=bool(settings.EMBEDDING_NORMALIZE),
    )
    return np.asarray(arr, dtype=np.float32)


def serialize_f32(vec: np.ndarray) -> bytes:
    return np.ascontiguousarray(vec, dtype=np.float32).tobytes()


def deserialize_f32(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32, count=dim)


def extract_fragments_from_scenario_packs(scenario_pack_id: str | None = None) -> list[dict]:
    rows = list_scenario_packs()
    out: list[dict] = []
    for row in rows:
        pack = row.get("pack_json") or {}
        if scenario_pack_id and pack.get("id") != scenario_pack_id:
            continue
        pack_id = pack.get("id") or row.get("id")
        scenario = pack.get("scenario") or row.get("scenario")
        title = pack.get("title") or row.get("slug", "pack")
        description = pack.get("description") or ""
        if description:
            out.append(
                {
                    "fragment_key": f"{scenario}:{pack_id}:description:v1",
                    "fragment_type": "pack_description",
                    "scenario": scenario,
                    "scenario_pack_id": pack_id,
                    "locale": "en",
                    "tags_json": [scenario, "description"],
                    "source_ref_json": {"source": "scenario_pack", "version": pack.get("version", "unknown")},
                    "content_text": f"{title}. {description}",
                }
            )
        for frag in (pack.get("fragments") or []):
            text = str(frag.get("text") or "").strip()
            if not text:
                continue
            fid = frag.get("id") or hashlib.md5(text.encode("utf-8")).hexdigest()[:12]  # noqa: S324
            out.append(
                {
                    "fragment_key": f"{scenario}:{pack_id}:{fid}:v1",
                    "fragment_type": frag.get("content_type") or "scenario_fragment",
                    "scenario": scenario,
                    "scenario_pack_id": pack_id,
                    "locale": "en",
                    "tags_json": list(frag.get("tags") or []),
                    "source_ref_json": {"source": "scenario_pack_fragment", "fragment_id": frag.get("id")},
                    "content_text": text,
                }
            )
    if not out:
        out.append(
            {
                "fragment_key": "default:default:seed:v1",
                "fragment_type": "scenario_fragment",
                "scenario": "workplace",
                "scenario_pack_id": "default",
                "locale": "en",
                "tags_json": ["workplace", "decision"],
                "source_ref_json": {"source": "fallback"},
                "content_text": "A stakeholder escalates an issue before a deadline and expects a clear response.",
            }
        )
    return out


def seed_embeddings(scenario_pack_id: str | None = None, force: bool = False) -> dict[str, Any]:
    fragments = extract_fragments_from_scenario_packs(scenario_pack_id=scenario_pack_id)
    texts = [f["content_text"] for f in fragments]
    import time

    started = time.perf_counter()
    vectors = embed_texts(texts)
    existing = {
        row.get("fragment_key"): row
        for row in list_fragment_embeddings_for_index(
            filters={"scenario_pack_id": scenario_pack_id} if scenario_pack_id else {"active": True}
        )
    }
    embedded = 0
    skipped = 0
    dim = int(vectors.shape[1]) if vectors.ndim == 2 and vectors.shape[1] else 0
    for i, frag in enumerate(fragments):
        csum = content_sha256(frag["content_text"])
        row = {
            "fragment_key": frag["fragment_key"],
            "fragment_type": frag["fragment_type"],
            "scenario": frag.get("scenario"),
            "scenario_pack_id": frag.get("scenario_pack_id"),
            "locale": frag.get("locale"),
            "tags_json": frag.get("tags_json") or [],
            "source_ref_json": frag.get("source_ref_json") or {},
            "content_text": frag["content_text"],
            "content_sha256": csum,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_revision": settings.EMBEDDING_REVISION or None,
            "embedding_dim": dim,
            "embedding_f32": serialize_f32(vectors[i]),
            "normalized": bool(settings.EMBEDDING_NORMALIZE),
            "active": True,
        }
        prev = existing.get(row["fragment_key"]) or {}
        upsert_fragment_embedding(row)
        if force or prev.get("content_sha256") != csum or prev.get("embedding_model") != settings.EMBEDDING_MODEL:
            embedded += 1
        else:
            skipped += 1
    log_event("embeddings_seeded", fragments_seen=len(fragments), embedded=embedded, skipped_unchanged=skipped)
    elapsed = max(1e-9, time.perf_counter() - started)
    record_embedding_throughput(settings.EMBEDDING_MODEL, settings.EMBEDDING_DEVICE, len(texts) / elapsed)
    return {
        "fragments_seen": len(fragments),
        "embedded": embedded,
        "skipped_unchanged": skipped,
        "model": settings.EMBEDDING_MODEL,
        "dim": dim,
    }
