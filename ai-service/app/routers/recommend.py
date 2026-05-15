from fastapi import APIRouter, Query
from typing import Optional
from app.services import hybrid_service, cb_service, als_service

router = APIRouter()


@router.post("/invalidate-cb-cache")
async def invalidate_cb_cache():
    """Xóa cache content vector trong RAM → lần sau tự reload từ MongoDB."""
    await cb_service.invalidate_cache()
    return {"status": "ok", "message": "CB cache cleared. Will reload from MongoDB on next request."}



@router.get("/hybrid-recommend")
async def hybrid_recommend(
    user_id: str,
    recent_tracks: Optional[str] = Query(default=""),
):
    """
    Hybrid recommendation (trang chu):
    Ket hop CF (daily_recommendations) + CB (recent tracks similarity)
    """
    recent_ids = [t.strip() for t in recent_tracks.split(",") if t.strip()] if recent_tracks else []
    track_ids = await hybrid_service.hybrid_recommend(user_id, recent_ids)
    return {"track_ids": track_ids, "count": len(track_ids)}


@router.get("/als-recommend")
async def als_recommend(
    user_id: str,
    top_k: int = Query(default=30, le=50),
):
    """
    Collaborative Filtering only (tab Collab Picks):
    Tra ve goi y tu ALS model, khong ket hop content-based.
    Fallback: popular tracks neu user chua co du lieu.
    """
    track_ids = await als_service.get_cf_recommendations(user_id, top_n=top_k)
    return {"track_ids": track_ids, "count": len(track_ids), "strategy": "collaborative"}


@router.get("/content-recommend")
async def content_recommend(
    user_id: str,
    recent_tracks: Optional[str] = Query(default=""),
    genres: Optional[str] = Query(default=""),
    top_k: int = Query(default=30, le=50),
):
    """
    Content-Based only (tab Taste Match):
    Dua tren audio features cua bai vua nghe.
    Fallback cold-start (theo genre) neu user chua co lich su nghe.
    """
    recent_ids = [t.strip() for t in recent_tracks.split(",") if t.strip()] if recent_tracks else []

    if recent_ids:
        cb_scores: dict = {}
        for recent_id in recent_ids[:5]:
            try:
                similar = await cb_service.get_similar_tracks(
                    recent_id, top_k=top_k, exclude_ids=recent_ids
                )
                for item in similar:
                    tid = item["track_id"]
                    cb_scores[tid] = cb_scores.get(tid, 0.0) + item["score"] / len(recent_ids[:5])
            except Exception:
                pass
        scored = sorted(cb_scores.items(), key=lambda x: x[1], reverse=True)
        track_ids = [tid for tid, _ in scored[:top_k]]
        return {"track_ids": track_ids, "count": len(track_ids), "strategy": "content_based"}

    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []
    track_ids = await hybrid_service.cold_start(genre_list, top_k=top_k)
    return {"track_ids": track_ids, "count": len(track_ids), "strategy": "cold_start"}


@router.get("/cold-start")
async def cold_start(
    genres: Optional[str] = Query(default=""),
    top_k: int = Query(default=30, le=50),
):
    """Cold-Start: popular tracks theo genre"""
    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []
    track_ids = await hybrid_service.cold_start(genre_list, top_k=top_k)
    return {"track_ids": track_ids, "strategy": "cold_start", "count": len(track_ids)}


@router.get("/content-similar")
async def content_similar(
    track_id: str,
    user_id: Optional[str] = Query(default=None),
    top_k: int = Query(default=5, le=20),
    exclude: Optional[str] = Query(default=""),
):
    """
    Hybrid similar tracks (popup khi dang nghe nhac):
    Co user_id -> hybrid (CB + CF). Khong co user -> CB thuan.
    """
    exclude_ids = [t.strip() for t in exclude.split(",") if t.strip()] if exclude else []

    if user_id:
        recent_ids = [track_id] + exclude_ids[:2]
        hybrid_ids = await hybrid_service.hybrid_recommend(user_id, recent_ids)
        exclude_set = set(exclude_ids) | {track_id}
        filtered = [tid for tid in hybrid_ids if tid not in exclude_set][:top_k]
        results = [{"track_id": tid, "score": round(1.0 - i * 0.05, 3)} for i, tid in enumerate(filtered)]
        return {"similar_tracks": results, "source_track_id": track_id, "strategy": "hybrid"}
    else:
        results = await cb_service.get_similar_tracks(track_id, top_k=top_k, exclude_ids=exclude_ids)
        return {"similar_tracks": results, "source_track_id": track_id, "strategy": "content_based"}
