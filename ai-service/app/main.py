from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import train, recommend, evaluate
from app.services import als_service
import logging

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Auto-load ALS model from disk on startup (no need to retrain every restart)."""
    try:
        als_service._load_model_from_disk()
        log.info("[startup] ALS model loaded from disk successfully.")
    except Exception as e:
        log.warning(f"[startup] Could not load ALS model: {e}. Will need to train first.")
    yield
    # shutdown


app = FastAPI(title="MusicRec AI Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(train.router,     prefix="/ai", tags=["Training"])
app.include_router(recommend.router, prefix="/ai", tags=["Recommendations"])
app.include_router(evaluate.router,  prefix="/ai", tags=["Evaluation"])

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-service"}
