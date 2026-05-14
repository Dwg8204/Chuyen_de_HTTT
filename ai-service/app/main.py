from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import train, recommend, evaluate

app = FastAPI(title="MusicRec AI Service", version="1.0.0")

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
