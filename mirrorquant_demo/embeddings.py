"""Text embedding provider for the knowledge-base vector store.

Backend selection via ``MIRRORQUANT_EMBEDDING_BACKEND``:
  - ``auto`` (default) — use sentence-transformers if installed, else the
    deterministic hashing fallback.
  - ``sentence-transformers`` — force the ST model (raises if unavailable).
  - ``hashing`` — force the offline hashing embedding.

The hashing fallback (feature-hashing / "hashing trick") needs only NumPy, runs
fully offline with no model download, and is deterministic — so the vector store
always works, even with no extra dependencies or network. Each embedding is
tagged with :func:`backend_name` so the retrieval layer only compares vectors
produced by the same backend (and falls back to TF-IDF otherwise).
"""

from __future__ import annotations

import os
import re

import numpy as np

BACKEND = os.getenv("MIRRORQUANT_EMBEDDING_BACKEND", "auto").strip().lower()
ST_MODEL_NAME = os.getenv("MIRRORQUANT_EMBEDDING_MODEL", "all-MiniLM-L6-v2").strip()
HASH_DIM = int(os.getenv("MIRRORQUANT_EMBEDDING_HASH_DIM", "256"))

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_st_model = None          # lazily loaded SentenceTransformer instance
_resolved_backend = None  # cached concrete backend name, e.g. "st:all-MiniLM-L6-v2"


def _try_load_st():
    """Return a cached SentenceTransformer, or None if unavailable."""
    global _st_model
    if _st_model is not None:
        return _st_model
    try:
        from sentence_transformers import SentenceTransformer
    except Exception:  # ImportError or backend init issues
        return None
    try:
        _st_model = SentenceTransformer(ST_MODEL_NAME)
    except Exception:  # model download/load failure -> fall back
        return None
    return _st_model


def _use_sentence_transformers() -> bool:
    if BACKEND == "hashing":
        return False
    model = _try_load_st()
    if model is None:
        if BACKEND == "sentence-transformers":
            raise RuntimeError(
                "sentence-transformers backend requested but unavailable; "
                "install it or set MIRRORQUANT_EMBEDDING_BACKEND=hashing"
            )
        return False
    return True


def backend_name() -> str:
    """Concrete backend identifier, stored alongside each embedding."""
    global _resolved_backend
    if _resolved_backend is None:
        _resolved_backend = (
            f"st:{ST_MODEL_NAME}" if _use_sentence_transformers() else f"hash:{HASH_DIM}"
        )
    return _resolved_backend


def dimension() -> int:
    if backend_name().startswith("hash:"):
        return HASH_DIM
    return int(_try_load_st().get_sentence_embedding_dimension())


def _hash_embed_one(text: str) -> np.ndarray:
    """Deterministic feature-hashing embedding (signed), L2-normalised."""
    vec = np.zeros(HASH_DIM, dtype=np.float32)
    for token in _TOKEN_RE.findall((text or "").lower()):
        h = hash_token(token)
        idx = h % HASH_DIM
        sign = 1.0 if (h >> 31) & 1 == 0 else -1.0
        vec[idx] += sign
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec /= norm
    return vec


def hash_token(token: str) -> int:
    """Stable non-cryptographic hash (FNV-1a, 32-bit) — independent of PYTHONHASHSEED."""
    h = 2166136261
    for ch in token.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts with the active backend."""
    if not texts:
        return []
    if backend_name().startswith("st:"):
        model = _try_load_st()
        arr = model.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
        return [row.astype(np.float32).tolist() for row in np.atleast_2d(arr)]
    return [_hash_embed_one(t).tolist() for t in texts]


def embed_query(text: str) -> list[float]:
    out = embed_texts([text or ""])
    return out[0] if out else []


def cosine(query: list[float], matrix: list[list[float]]) -> list[float]:
    """Cosine similarity of one query vector against a list of vectors."""
    if not matrix or not query:
        return []
    q = np.asarray(query, dtype=np.float32)
    m = np.asarray(matrix, dtype=np.float32)
    qn = float(np.linalg.norm(q))
    if qn == 0:
        return [0.0] * len(matrix)
    q = q / qn
    mn = np.linalg.norm(m, axis=1)
    mn[mn == 0] = 1.0
    m = m / mn[:, None]
    return (m @ q).astype(float).tolist()
