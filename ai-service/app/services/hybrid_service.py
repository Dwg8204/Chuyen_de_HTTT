"""
hybrid_service.py - Kết hợp CF + CB theo công thức Weighted Hybrid
"""
import logging
import numpy as np
from app.database import get_db
from app.services import als_service, cb_service

log = logging.getLogger(__name__)

ALPHA = 0.6   # Trọng số CB (bài vừa nghe)
TOP_N = 30    # Số bài trả về cuối cùng


async def cold_start(genres: list[str], top_k: int = 30) -> list[str]:
    """
    Chiến lược Cold-Start:
      1. Lọc tracks có genre ∩ genres != ∅
      2. Sắp xếp theo total_plays giảm dần
      3. Trả về top_k track_id strings
    """
    db = get_db()
    query = {"genre": {"$in": genres}} if genres else {}
    cursor = db.tracks.find(query, {"_id": 1}).sort("total_plays", -1).limit(top_k)
    ids = []
    async for doc in cursor:
        ids.append(str(doc["_id"]))
    return ids


async def hybrid_recommend(user_id: str, recent_track_ids: list[str]) -> list[str]:
    """
    Hybrid recommendation:
      - Lấy CF scores từ daily_recommendations
      - Lấy CB scores từ content similarity với recent tracks
      - Trộn: score_final = alpha * score_CB + (1-alpha) * score_CF
      - Trả về top TOP_N track_ids
    """
    # ── CF part ──────────────────────────────────────────────────────────────
    cf_list = await als_service.get_cf_recommendations(user_id, top_n=50)
    # Normalize CF rank score: rank 1 = 1.0, rank 50 = 0.0
    cf_scores: dict[str, float] = {}
    n_cf = len(cf_list)
    for rank, tid in enumerate(cf_list):
        cf_scores[tid] = 1.0 - (rank / max(n_cf, 1))

    # ── CB part ───────────────────────────────────────────────────────────────
    cb_scores: dict[str, float] = {}
    for recent_id in recent_track_ids[:3]:    # Dùng tối đa 3 bài gần nhất
        try:
            similar = await cb_service.get_similar_tracks(recent_id, top_k=20, exclude_ids=recent_track_ids)
            for item in similar:
                tid = item["track_id"]
                # Average nếu xuất hiện từ nhiều recent tracks
                cb_scores[tid] = cb_scores.get(tid, 0.0) + item["score"] / len(recent_track_ids[:3])
        except Exception as e:
            log.warning(f"CB error for track {recent_id}: {e}")

    # ── Merge all candidate track IDs ─────────────────────────────────────────
    all_candidates = set(cf_scores.keys()) | set(cb_scores.keys())
    exclude = set(recent_track_ids)

    scored = []
    for tid in all_candidates:
        if tid in exclude:
            continue
        s_cb = cb_scores.get(tid, 0.0)
        s_cf = cf_scores.get(tid, 0.0)
        final = ALPHA * s_cb + (1 - ALPHA) * s_cf
        scored.append((tid, final))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [tid for tid, _ in scored[:TOP_N]]
