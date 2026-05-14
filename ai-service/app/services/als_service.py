"""
als_service.py - Collaborative Filtering dùng ALS (implicit library)

Cải tiến:
  - Confidence weighting: c_ui = 1 + ALPHA * log(1 + play_count)
  - Lọc user thưa (< MIN_USER_INTERACTIONS)
  - Lọc item thưa (< MIN_ITEM_PLAYS)
  - Manual filter thay filter_already_liked_items để tránh IndexError
"""
import logging, time, os, pickle, math
from collections import defaultdict
from datetime import datetime, timezone
import numpy as np
import scipy.sparse as sp
from implicit.als import AlternatingLeastSquares
from app.database import get_db

# Fix OpenBLAS thread warning
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

log = logging.getLogger(__name__)
MODEL_PATH = "models/als_model.pkl"
os.makedirs("models", exist_ok=True)

# ── Hyperparameters (cập nhật sau khi Grid Search tìm ra best params) ─────────
ALPHA                  = 40.0   # Confidence scale: c = 1 + ALPHA * log(1 + cnt)
MIN_USER_UNIQUE_TRACKS = 15     # Lọc user có < 15 bài KHÁC NHAU (không phải tổng plays)
MIN_ITEM_PLAYS         = 50     # Lọc track có tổng plays < ngưỡng

# In-memory model cache
_model: AlternatingLeastSquares | None = None
_user_map: dict = {}   # user_id_str -> matrix row index
_item_map: dict = {}   # track_id_str -> matrix col index
_rev_item: dict = {}   # matrix col index -> track_id_str
_liked_map: dict = {}  # user_id_str -> set of item col indices (để filter)


async def train_model() -> dict:
    """Train ALS với confidence weighting + data filtering."""
    global _model, _user_map, _item_map, _rev_item, _liked_map

    db = get_db()
    t0 = time.time()
    log.info("Loading interactions from MongoDB …")

    # ── Bước 1: Load toàn bộ interactions ─────────────────────────────────────
    all_interactions = []
    async for doc in db.interactions.find(
        {}, {"user_id": 1, "track_id": 1, "play_count": 1}
    ):
        all_interactions.append((
            str(doc["user_id"]),
            str(doc["track_id"]),
            float(doc.get("play_count", 1)),
        ))

    if not all_interactions:
        return {"status": "error", "message": "No interaction data found"}

    # ── Bước 2: Đếm unique tracks/item plays ──────────────────────────────────
    user_unique: dict = defaultdict(set)    # uid -> set of unique iid
    item_total:  dict = defaultdict(float)  # iid -> tổng plays
    for uid, iid, cnt in all_interactions:
        user_unique[uid].add(iid)           # đếm UNIQUE bài, không cộng cnt
        item_total[iid] += cnt

    # ── Bước 3: Lọc user theo số bài UNIQUE (không phải tổng play_count) ───────
    active_users  = {u for u, s in user_unique.items() if len(s) >= MIN_USER_UNIQUE_TRACKS}
    popular_items = {i for i, c in item_total.items()  if c >= MIN_ITEM_PLAYS}

    filtered = [
        (uid, iid, cnt)
        for uid, iid, cnt in all_interactions
        if uid in active_users and iid in popular_items
    ]

    log.info(f"Users: {len(user_unique):,} → {len(active_users):,} (>= {MIN_USER_UNIQUE_TRACKS} unique tracks)")
    log.info(f"Items: {len(item_total):,} → {len(popular_items):,} (>= {MIN_ITEM_PLAYS} total plays)")
    log.info(f"Interactions: {len(all_interactions):,} → {len(filtered):,}")


    if not filtered:
        return {"status": "error", "message": "No interactions after filtering"}

    # ── Bước 4: Aggregate play counts per (user, item) ─────────────────────────
    # (một user có thể có nhiều docs cho cùng 1 track)
    agg: dict = defaultdict(float)
    user_set, item_set = {}, {}
    for uid, iid, cnt in filtered:
        if uid not in user_set: user_set[uid] = len(user_set)
        if iid not in item_set: item_set[iid] = len(item_set)
        agg[(user_set[uid], item_set[iid])] += cnt

    n_users = len(user_set)
    n_items = len(item_set)
    log.info(f"Matrix: {n_users} users × {n_items} items")

    # ── Bước 5: Build confidence matrix ───────────────────────────────────────
    # c_ui = 1 + ALPHA * log(1 + play_count)
    rows_u, rows_i, conf_data = [], [], []
    liked_by_user: dict = defaultdict(set)   # u_idx -> set of i_idx

    for (u_idx, i_idx), cnt in agg.items():
        rows_u.append(u_idx)
        rows_i.append(i_idx)
        conf_data.append(1.0 + ALPHA * math.log1p(cnt))
        liked_by_user[u_idx].add(i_idx)

    user_items = sp.csr_matrix(
        (conf_data, (rows_u, rows_i)),
        shape=(n_users, n_items), dtype=np.float32,
    )
    item_users = user_items.T.tocsr()

    # ── Bước 6: Train ALS ─────────────────────────────────────────────────────
    # Tham số sẽ được cập nhật sau khi Grid Search hoàn thành
    model = AlternatingLeastSquares(
        factors=128, iterations=30, regularization=0.1,
        random_state=42, num_threads=1,
    )
    model.fit(item_users)

    # ── Bước 7: Store mappings ─────────────────────────────────────────────────
    _model    = model
    _user_map = user_set
    _item_map = item_set
    _rev_item = {v: k for k, v in item_set.items()}
    _liked_map = {
        uid_str: liked_by_user.get(user_set[uid_str], set())
        for uid_str in user_set
    }

    # ── Bước 8: Generate recommendations cho mọi user ─────────────────────────
    log.info("Generating recommendations for all users …")
    ops = []

    for uid_str, u_idx in user_set.items():
        row   = user_items[u_idx]
        liked = liked_by_user.get(u_idx, set())

        try:
            req_n   = min(50 + len(liked), n_items - 1)
            ids_arr, scores_arr = model.recommend(
                u_idx, row, N=req_n, filter_already_liked_items=False
            )
            # Manual filter: loại bỏ bài đã nghe
            pairs     = [(int(i), float(s)) for i, s in zip(ids_arr, scores_arr) if int(i) not in liked]
            track_ids = [_rev_item[i] for i, _ in pairs[:50]]
            scores    = [s for _, s in pairs[:50]]
        except Exception as e:
            log.warning(f"recommend() failed for {uid_str}: {e}")
            track_ids, scores = [], []

        ops.append({
            "filter": {"user_id": uid_str},
            "update": {"$set": {
                "user_id":     uid_str,
                "track_ids":   track_ids,
                "scores":      scores,
                "computed_at": datetime.now(timezone.utc),
            }},
            "upsert": True,
        })

    if ops:
        from pymongo import UpdateOne
        bulk = [UpdateOne(o["filter"], o["update"], upsert=o["upsert"]) for o in ops]
        await db.daily_recommendations.bulk_write(bulk)

    # ── Bước 9: Lưu model ra disk ──────────────────────────────────────────────
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({
            "model":     model,
            "user_map":  _user_map,
            "item_map":  _item_map,
            "rev_item":  _rev_item,
            "liked_map": _liked_map,
        }, f)

    duration = round(time.time() - t0, 2)
    log.info(f"Training done in {duration}s")
    return {
        "status":           "done",
        "users_processed":  n_users,
        "items":            n_items,
        "interactions":     len(filtered),
        "duration_seconds": duration,
    }


def _load_model_from_disk():
    global _model, _user_map, _item_map, _rev_item, _liked_map
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            saved = pickle.load(f)
        _model     = saved["model"]
        _user_map  = saved["user_map"]
        _item_map  = saved["item_map"]
        _rev_item  = saved["rev_item"]
        _liked_map = saved.get("liked_map", {})
        log.info("ALS model loaded from disk")


async def get_cf_recommendations(user_id: str, top_n: int = 50) -> list[str]:
    """Lấy CF recommendations từ daily_recommendations collection"""
    if _model is None:
        _load_model_from_disk()

    db = get_db()
    doc = await db.daily_recommendations.find_one({"user_id": user_id})
    if doc:
        return doc.get("track_ids", [])[:top_n]
    return []
