"""
update_content_vectors.py
Cập nhật content_vector 7D → 12D mà KHÔNG cần chạy lại 01_preprocess.py.
- Đọc Music Info.csv (nhỏ, nhanh)
- Cập nhật tracks.json (thêm 5 features mới)
- Cập nhật MongoDB (upsert content_vector cho từng track)
- Invalidate CB cache trên AI service

Chạy: cd data && python update_content_vectors.py
"""
import json, os, sys, logging, asyncio
import pandas as pd
import numpy as np
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

BASE           = os.path.dirname(os.path.abspath(__file__))
MUSIC_CSV      = os.path.join(BASE, "raw", "Music Info.csv")
TRACKS_JSON    = os.path.join(BASE, "processed", "tracks.json")
MONGO_URI      = "mongodb://localhost:27017"
DB_NAME        = "musicrec"
AI_SERVICE_URL = "http://localhost:8000"


# ── 1. Helper ─────────────────────────────────────────────────────────────────
def safe_float(val, default=0.0):
    try:   return float(val)
    except: return default


def build_content_vector(row: dict) -> list:
    """12-dimensional content vector từ audio features."""
    loudness_norm = (safe_float(row.get("loudness", -30)) + 60) / 60
    loudness_norm = max(0.0, min(1.0, loudness_norm))
    return [
        safe_float(row.get("danceability",      .5)),         # 1
        safe_float(row.get("energy",            .5)),         # 2
        safe_float(row.get("valence",           .5)),         # 3
        safe_float(row.get("tempo",           120)) / 250.0,  # 4
        safe_float(row.get("acousticness",      .5)),         # 5
        safe_float(row.get("liveness",          .5)),         # 6
        safe_float(row.get("speechiness",       .5)),         # 7
        safe_float(row.get("instrumentalness",   0)),         # 8
        loudness_norm,                                         # 9
        safe_float(row.get("mode",               1)),         # 10
        safe_float(row.get("key",                5)) / 11.0,  # 11
        (safe_float(row.get("time_signature",    4)) - 1) / 7.0,  # 12
    ]



def build_audio_features(row: dict) -> dict:
    keys = ["danceability","energy","valence","tempo","acousticness",
            "liveness","speechiness","instrumentalness","loudness",
            "mode","key","time_signature"]
    return {k: safe_float(row.get(k, 0.0)) for k in keys}


# ── 2. Load Music Info.csv ────────────────────────────────────────────────────
def load_music_info() -> pd.DataFrame:
    log.info(f"[1] Reading Music Info.csv ...")
    df = pd.read_csv(MUSIC_CSV, dtype=str)
    rename = {}
    if "name" in df.columns: rename["name"] = "title"
    df = df.rename(columns=rename)
    df = df.dropna(subset=["track_id"]).drop_duplicates("track_id")
    log.info(f"    {len(df):,} tracks loaded from CSV")
    return df


# ── 3. Update tracks.json ─────────────────────────────────────────────────────
def update_tracks_json(df: pd.DataFrame):
    log.info(f"[2] Updating tracks.json ...")
    with open(TRACKS_JSON, encoding="utf-8") as f:
        tracks = json.load(f)

    # Build lookup: track_id_str -> row dict from CSV
    csv_map = {str(row["track_id"]): row.to_dict() for _, row in df.iterrows()}

    updated = 0
    for t in tqdm(tracks, desc="Recomputing vectors"):
        tid = t.get("track_id_str", "")
        row = csv_map.get(tid)
        if row:
            t["content_vector"]  = build_content_vector(row)
            t["audio_features"]  = build_audio_features(row)
            updated += 1

    with open(TRACKS_JSON, "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False)

    log.info(f"    Updated {updated:,} / {len(tracks):,} tracks in tracks.json")
    return tracks


# ── 4. Update MongoDB ─────────────────────────────────────────────────────────
async def update_mongodb(tracks: list):
    try:
        import motor.motor_asyncio
    except ImportError:
        log.warning("motor not installed. Skipping MongoDB update.")
        log.warning("Run: pip install motor  then re-run this script.")
        return

    log.info(f"[3] Connecting to MongoDB ({MONGO_URI}) ...")
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    from pymongo import UpdateOne
    ops = []
    for t in tqdm(tracks, desc="Building MongoDB ops"):
        tid_str = t.get("track_id_str", "")
        cv      = t.get("content_vector")
        af      = t.get("audio_features", {})
        if not cv: continue
        ops.append(UpdateOne(
            {"track_id_str": tid_str},
            {"$set": {"content_vector": cv, "audio_features": af}},
        ))

    if ops:
        result = await db.tracks.bulk_write(ops, ordered=False)
        log.info(f"    MongoDB: matched={result.matched_count:,} | modified={result.modified_count:,}")
    else:
        log.warning("    No ops to write!")

    client.close()


# ── 5. Invalidate CB cache ────────────────────────────────────────────────────
async def invalidate_cb_cache():
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{AI_SERVICE_URL}/ai/invalidate-cb-cache",
                                    timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    log.info("[4] CB cache invalidated via API ✅")
                else:
                    log.warning(f"[4] CB cache invalidation returned {resp.status}")
    except Exception as e:
        log.warning(f"[4] Could not call AI service ({e}). Restart ai-service manually to reload cache.")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    df     = load_music_info()
    tracks = update_tracks_json(df)
    await update_mongodb(tracks)
    await invalidate_cb_cache()
    log.info("\n✅ Done! Content vectors updated: 7D → 12D")
    log.info("   CB model will reload automatically on next request.")
    log.info("   (ALS model unchanged — no retrain needed)")


if __name__ == "__main__":
    asyncio.run(main())
