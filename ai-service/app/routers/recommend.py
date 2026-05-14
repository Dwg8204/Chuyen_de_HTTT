from fastapi import APIRouter, Query
from typing import Optional
from app.services import hybrid_service, cb_service

router = APIRouter()


@router.get("/hybrid-recommend")
async def hybrid_recommend(
    user_id: str,
    recent_tracks: Optional[str] = Query(default=""),   # comma-separated track_ids
):
    """
    Hybrid recommendation:
    Kết hợp CF (daily_recommendations) + CB (recent tracks similarity)
    """
    recent_ids = [t.strip() for t in recent_tracks.split(",") if t.strip()] if recent_tracks else []
    track_ids = await hybrid_service.hybrid_recommend(user_id, recent_ids)
    return {"track_ids": track_ids, "count": len(track_ids)}


@router.get("/cold-start")
async def cold_start(
    genres: Optional[str] = Query(default=""),   # comma-separated
    top_k: int = Query(default=30, le=50),
):
    """
    Cold-Start: Trả về bài nổi tiếng nhất theo genre preferences
    """
    genre_list = [g.strip() for g in genres.split(",") if g.strip()] if genres else []
    track_ids = await hybrid_service.cold_start(genre_list, top_k=top_k)
    return {"track_ids": track_ids, "strategy": "cold_start", "count": len(track_ids)}


@router.get("/content-similar")
async def content_similar(
    track_id: str,
    top_k: int = Query(default=5, le=20),
    exclude: Optional[str] = Query(default=""),   # comma-separated
):
    """
    Real-time Content-Based: Trả về top_k bài tương tự nhất
    (dùng cho floating popup khi đang nghe nhạc)
    """
    exclude_ids = [t.strip() for t in exclude.split(",") if t.strip()] if exclude else []
    results = await cb_service.get_similar_tracks(track_id, top_k=top_k, exclude_ids=exclude_ids)
    return {"similar_tracks": results, "source_track_id": track_id}
