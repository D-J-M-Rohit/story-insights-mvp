import json
import os
import random
import time

import numpy as np

from app.benchmarks import percentile


def _synthetic_corpus(n: int) -> list[str]:
    words = ["deadline", "team", "stakeholder", "tradeoff", "risk", "support", "priority", "conflict", "review", "escalation"]
    out = []
    for i in range(n):
        out.append(" ".join(random.choice(words) for _ in range(24)) + f" #{i}")
    return out


def main():
    model_name = os.getenv("MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
    n = int(os.getenv("N", "100000"))
    q = int(os.getenv("Q", "200"))
    k = int(os.getenv("K", "10"))
    batch_size = int(os.getenv("BATCH_SIZE", "64"))
    hnsw_m = int(os.getenv("HNSW_M", "32"))
    ef_construction = int(os.getenv("EF_CONSTRUCTION", "200"))
    ef_search = int(os.getenv("EF_SEARCH", "64"))

    from sentence_transformers import SentenceTransformer
    import faiss

    corpus = _synthetic_corpus(n)
    model = SentenceTransformer(model_name)
    t0 = time.perf_counter()
    embs = model.encode(corpus, batch_size=batch_size, convert_to_numpy=True, normalize_embeddings=True)
    embs = np.asarray(embs, dtype=np.float32)
    t_embed = time.perf_counter() - t0
    dim = embs.shape[1]

    t1 = time.perf_counter()
    index = faiss.IndexIDMap2(faiss.IndexHNSWFlat(dim, hnsw_m, faiss.METRIC_INNER_PRODUCT))
    index.hnsw.efConstruction = ef_construction
    index.hnsw.efSearch = ef_search
    ids = np.arange(1, n + 1, dtype=np.int64)
    index.add_with_ids(embs, ids)
    t_build = time.perf_counter() - t1

    queries = embs[np.random.choice(n, size=q, replace=False)]
    times_ms = []
    for i in range(q):
        s = time.perf_counter()
        index.search(queries[i : i + 1], k)
        times_ms.append((time.perf_counter() - s) * 1000.0)

    out = {
        "model": model_name,
        "n_vectors": n,
        "dim": dim,
        "batch_size": batch_size,
        "embedding_seconds": t_embed,
        "embedding_vectors_per_sec": n / max(1e-9, t_embed),
        "index_build_seconds": t_build,
        "search_samples": q,
        "k": k,
        "search_p50_ms": percentile(times_ms, 0.50),
        "search_p95_ms": percentile(times_ms, 0.95),
        "search_p99_ms": percentile(times_ms, 0.99),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
