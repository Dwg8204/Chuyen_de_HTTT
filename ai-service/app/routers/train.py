import asyncio
from fastapi import APIRouter, BackgroundTasks
from app.services import als_service

router = APIRouter()

# Track training state
_training_state = {"status": "idle", "message": "", "result": None}


async def _run_training():
    global _training_state
    _training_state = {"status": "running", "message": "Training in progress...", "result": None}
    try:
        result = await als_service.train_model()
        _training_state = {"status": "done", "message": "Training completed", "result": result}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        _training_state = {"status": "error", "message": str(e), "traceback": tb, "result": None}


@router.post("/train")
async def trigger_training(background_tasks: BackgroundTasks):
    """Trigger ALS model training in background (won't timeout)"""
    global _training_state
    if _training_state["status"] == "running":
        return {"status": "already_running", "message": "Training is already in progress"}
    background_tasks.add_task(_run_training)
    _training_state = {"status": "started", "message": "Training started in background"}
    return {"status": "started", "message": "Training started. Check /ai/train/status for progress."}


@router.get("/train/status")
async def training_status():
    """Poll training status"""
    return _training_state
