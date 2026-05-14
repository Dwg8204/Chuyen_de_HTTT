from fastapi import APIRouter
from app.services import als_service

router = APIRouter()

@router.post("/train")
async def trigger_training():
    """Trigger ALS model training (called by Admin Dashboard)"""
    result = await als_service.train_model()
    return result
