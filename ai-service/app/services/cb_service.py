"""
cb_service.py - Content-Based Filtering dùng Cosine Similarity
"""
import logging
import numpy as np
from app.database import get_db

log = logging.getLogger(__name__)

# In-memory vector cache
_vectors: np.ndarray | None = None   # shape (n_tracks, 7)
_track_ids: list[str]       = []     # MongoDB _id strings, index-aligned with _vectors
_track_str_ids: list[str]   = []     # track_id_str values


async def _ensure_cache():
    global _vectors, _track_ids, _track_str_ids
    if _vectors is not None:
        return

    log.info("Loading content vectors from MongoDB …")
    db = get_db()
    cursor = db.tracks.find({}, {"_id": 1, "content_vector": 1})
    ids, vecs = [], []
    async for doc in cursor:
        v = doc.get("content_vector")
        if v and len(v) >= 7:    # hỗ trợ cả vector 7D (cũ) lẫn 12D (mới)
            ids.append(str(doc["_id"]))
            vecs.append(v)

    if not vecs:
        log.warning("No content vectors found in tracks collection")
        return

    _track_ids = ids
    _vectors   = np.array(vecs, dtype=np.float32)
    # L2-normalize for cosine similarity via dot product
    norms = np.linalg.norm(_vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    _vectors /= norms
    log.info(f"Cached {len(_track_ids)} content vectors | dim={_vectors.shape[1]}")


def _cosine_similarities(query_vec: list[float]) -> np.ndarray:
    """Tính cosine similarity giữa query và toàn bộ ma trận (đã normalize)"""
    q = np.array(query_vec, dtype=np.float32)
    norm = np.linalg.norm(q)
    if norm > 0:
        q /= norm
    return _vectors @ q   # dot product of normalized vectors = cosine similarity


async def get_similar_tracks(track_id: str, top_k: int = 10, exclude_ids: list[str] | None = None) -> list[dict]:
    """
    Trả về top_k bài hát tương tự track_id nhất theo content vector.
    Mỗi item: { track_id: str, score: float }
    """
    await _ensure_cache()
    if _vectors is None or not _track_ids:
        return []

    exclude = set(exclude_ids or [])
    exclude.add(track_id)

    # Fetch query vector
    db = get_db()
    doc = await db.tracks.find_one({"_id": __import__("bson").ObjectId(track_id)}, {"content_vector": 1})
    if not doc or not doc.get("content_vector"):
        return []

    sims = _cosine_similarities(doc["content_vector"])
    # Sort descending
    ranked_idxs = np.argsort(-sims)

    results = []
    for idx in ranked_idxs:
        tid = _track_ids[idx]
        if tid in exclude:
            continue
        results.append({"track_id": tid, "score": float(sims[idx])})
        if len(results) >= top_k:
            break

    return results


async def invalidate_cache():
    """Xóa cache để reload lần sau (gọi sau khi seed lại data)"""
    global _vectors, _track_ids, _track_str_ids
    _vectors     = None
    _track_ids   = []
    _track_str_ids = []
    log.info("Content vector cache invalidated")
