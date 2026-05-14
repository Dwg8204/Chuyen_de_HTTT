import os
from fastapi import APIRouter
from fastapi.responses import FileResponse
from app.services import eval_service

router = APIRouter()


@router.get("/evaluate")
async def evaluate_cf():
    """Đánh giá CF model: NDCG@10, Recall@10/20, Precision@10/20, Coverage"""
    results = await eval_service.run_evaluation(k_values=[10, 20])
    return results


@router.get("/evaluate/cb")
async def evaluate_cb():
    """Đánh giá CB model: NDCG@10, Recall@10/20, Precision@10/20, Coverage"""
    results = await eval_service.run_cb_evaluation(k_values=[10, 20])
    return results


@router.get("/evaluate/chart")
async def get_cf_chart():
    """Trả về CF chart PNG gần nhất"""
    return _get_latest_chart("cf_metrics")


@router.get("/evaluate/chart/cb")
async def get_cb_chart():
    """Trả về CB chart PNG gần nhất"""
    return _get_latest_chart("cb_metrics")


def _get_latest_chart(prefix: str):
    eval_dir = "evaluation_results"
    if not os.path.exists(eval_dir):
        return {"error": "No evaluation results yet"}
    charts = sorted(
        [f for f in os.listdir(eval_dir) if f.startswith(prefix) and f.endswith(".png")],
        reverse=True
    )
    if not charts:
        return {"error": f"No {prefix} chart found – run evaluation first"}
    return FileResponse(os.path.join(eval_dir, charts[0]), media_type="image/png")
