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
from implicit.nearest_neighbours import bm25_weight
import implicit.evaluation
from app.database import get_db

# Fix OpenBLAS thread warning
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

log = logging.getLogger(__name__)
MODEL_PATH = "models/als_model.pkl"
os.makedirs("models", exist_ok=True)

# ── Hyperparameters (từ Grid Search) ──────────────────────────────────────────
FACTORS                = 64
ITERATIONS             = 20
REGULARIZATION         = 0.1
BM25_K1                = 1.0
BM25_B                 = 0.8
MIN_USER_UNIQUE_TRACKS = 30     # Lọc user có < 30 bài KHÁC NHAU
MIN_ITEM_PLAYS         = 30     # Lọc track có tổng plays < 50

# In-memory model cache
_model: AlternatingLeastSquares | None = None
_user_map: dict = {}   # user_id_str -> matrix row index
_item_map: dict = {}   # track_id_str -> matrix col index
_rev_item: dict = {}   # matrix col index -> track_id_str
_liked_map: dict = {}  # user_id_str -> set of item col indices (để filter)

def compute_recall_at_k(model, train_ui, test_ui, k=10) -> float:
    """Tính Recall@K thủ công trên toàn bộ test users (giống als_grid_search.py)."""
    recalls = []
    n_users = train_ui.shape[0]
    for u in range(n_users):
        test_row = test_ui[u]
        if test_row.nnz == 0: continue
        gt = set(test_row.indices.tolist())
        try:
            ids, _ = model.recommend(u, train_ui[u], N=k, filter_already_liked_items=True)
        except Exception:
            continue
        hit = len(set(ids.tolist()) & gt)
        recalls.append(hit / len(gt))
    return float(np.mean(recalls)) if recalls else 0.0


async def train_model() -> dict:
    """Train ALS với BM25 weighting + data filtering."""
    global _model, _user_map, _item_map, _rev_item, _liked_map

    db = get_db()
    t0 = time.time()
    log.info("Loading interactions from MongoDB …")

    # ── Bước 1: Load toàn bộ interactions (seed + real users) ─────────────────
    log.info("[1] Loading all interactions from MongoDB (seed data + real user plays)...")
    all_interactions = []
    async for doc in db.interactions.find(
        {}, {"user_id": 1, "track_id": 1, "play_count": 1}
    ):
        all_interactions.append((
            str(doc["user_id"]),
            str(doc["track_id"]),
            float(doc.get("play_count", 1)),
        ))

    log.info(f"[1] Total interactions loaded: {len(all_interactions):,}")

    # Lấy danh sách user thật (đăng ký trên hệ thống) — áp ngưỡng thấp hơn
    real_user_ids: set = set()
    async for doc in db.users.find({}, {"_id": 1}):
        real_user_ids.add(str(doc["_id"]))
    log.info(f"[1] Real registered users: {len(real_user_ids):,}")

    if not all_interactions:
        return {"status": "error", "message": "No interaction data found"}


    # ── Bước 2: Đếm unique tracks/item plays ──────────────────────────────────
    user_unique: dict = defaultdict(set)    # uid -> set of unique iid
    item_total:  dict = defaultdict(float)  # iid -> tổng plays
    for uid, iid, cnt in all_interactions:
        user_unique[uid].add(iid)           # đếm UNIQUE bài, không cộng cnt
        item_total[iid] += cnt

    # ── Bước 3: Lọc user và item ───────────────────────────────────────────────
    # User thật (đăng ký) dùng ngưỡng thấp hơn (>= 5 bài là đủ để include)
    MIN_REAL_USER_TRACKS = 5
    active_users = {
        u for u, s in user_unique.items()
        if len(s) >= (MIN_REAL_USER_TRACKS if u in real_user_ids else MIN_USER_UNIQUE_TRACKS)
    }
    popular_items = {i for i, c in item_total.items() if c >= MIN_ITEM_PLAYS}


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
    agg: dict = defaultdict(float)
    user_set, item_set = {}, {}
    liked_by_user: dict = defaultdict(set)

    for uid, iid, cnt in filtered:
        if uid not in user_set: user_set[uid] = len(user_set)
        if iid not in item_set: item_set[iid] = len(item_set)
        u_idx = user_set[uid]
        i_idx = item_set[iid]
        agg[(u_idx, i_idx)] += cnt
        liked_by_user[u_idx].add(i_idx)

    n_users = len(user_set)
    n_items = len(item_set)
    log.info(f"Matrix: {n_users} users × {n_items} items")

    # Build Sparse Matrix (user x item) chứa tổng play_count
    rows_u = [k[0] for k in agg]
    rows_i = [k[1] for k in agg]
    data   = list(agg.values())

    user_items = sp.csr_matrix(
        (data, (rows_u, rows_i)),
        shape=(n_users, n_items), dtype=np.float32,
    )

    # ── Bước 5: Đánh giá mô hình (Train/Test split 80/20) ───────────────────────
    try:
        import asyncio, concurrent.futures
        log.info("[Step 5] Train/Test split (80%%)...")
        train_ui, test_ui = implicit.evaluation.train_test_split(
            user_items, train_percentage=0.8, random_state=42
        )
        log.info(f"[Step 5] Train nnz: {train_ui.nnz:,} | Test nnz: {test_ui.nnz:,}")

        train_bm25 = bm25_weight(train_ui, K1=BM25_K1, B=BM25_B).tocsr()
        eval_model = AlternatingLeastSquares(
            factors=FACTORS, iterations=ITERATIONS, regularization=REGULARIZATION,
            random_state=42, num_threads=1
        )
        log.info("[Step 5] Fitting eval model...")
        eval_model.fit(train_bm25, show_progress=False)
        log.info("[Step 5] Eval model fitted. Computing ranking metrics...")

        m10 = implicit.evaluation.ranking_metrics_at_k(
            eval_model, train_ui, test_ui, K=10, show_progress=False, num_threads=1
        )
        m20 = implicit.evaluation.ranking_metrics_at_k(
            eval_model, train_ui, test_ui, K=20, show_progress=False, num_threads=1
        )
        log.info("[Step 5] Ranking metrics done. Computing Recall (may take a while)...")

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            r10 = await loop.run_in_executor(pool, compute_recall_at_k, eval_model, train_ui, test_ui, 10)
            r20 = await loop.run_in_executor(pool, compute_recall_at_k, eval_model, train_ui, test_ui, 20)

        log.info("=" * 60)
        log.info("   KET QUA DANH GIA (ALS Evaluation)")
        log.info("=" * 60)
        log.info(f"   NDCG@10      = {m10['ndcg']:.5f}")
        log.info(f"   Precision@10 = {m10['precision']:.5f}")
        log.info(f"   Recall@10    = {r10:.5f}")
        log.info(f"   NDCG@20      = {m20['ndcg']:.5f}")
        log.info(f"   Precision@20 = {m20['precision']:.5f}")
        log.info(f"   Recall@20    = {r20:.5f}")
        log.info("=" * 60)
    except Exception as eval_err:
        log.warning(f"[Step 5] Evaluation skipped due to error: {eval_err}")

    # ── Bước 6: Train ALS thực tế trên 100% dữ liệu ───────────────────────────
    log.info("🔄 Đang train lại model trên 100% dữ liệu để phục vụ Recommendations...")
    user_items_bm25 = bm25_weight(user_items, K1=BM25_K1, B=BM25_B).tocsr()

    model = AlternatingLeastSquares(
        factors=FACTORS,
        iterations=ITERATIONS,
        regularization=REGULARIZATION,
        random_state=42,
        num_threads=1,
    )
    model.fit(user_items_bm25)

    # ── Bước 7: Store mappings + user_items matrix for real-time inference ──────────
    _model     = model
    _user_map  = user_set
    _item_map  = item_set
    _rev_item  = {v: k for k, v in item_set.items()}
    _liked_map = {
        uid_str: liked_by_user.get(user_set[uid_str], set())
        for uid_str in user_set
    }

    # ── Bước 8: Lưu model + user_items matrix ra disk ─────────────────────────────
    global _user_items_matrix
    _user_items_matrix = user_items
    log.info("[Step 8] Saving model to disk...")
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({
            "model":      model,
            "user_map":   _user_map,
            "item_map":   _item_map,
            "rev_item":   _rev_item,
            "liked_map":  _liked_map,
            "user_items": user_items,
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


# ── Global user_items matrix (lưu để real-time inference) ─────────────────────
_user_items_matrix = None


def _load_model_from_disk():
    global _model, _user_map, _item_map, _rev_item, _liked_map, _user_items_matrix
    if os.path.exists(MODEL_PATH):
        with open(MODEL_PATH, "rb") as f:
            saved = pickle.load(f)
        _model             = saved["model"]
        _user_map          = saved["user_map"]
        _item_map          = saved["item_map"]
        _rev_item          = saved["rev_item"]
        _liked_map         = saved.get("liked_map", {})
        _user_items_matrix = saved.get("user_items", None)
        log.info(f"ALS model loaded from disk | {len(_user_map):,} users | {len(_item_map):,} items")


async def get_cf_recommendations(user_id: str, top_n: int = 50) -> list[str]:
    """
    Real-time CF recommendations với ALS Folding-in.

    Giữ nguyên item_factors đã train (không retrain).
    Fetch interaction hiện tại của user từ MongoDB → build BM25-weighted row
    → dùng recalculate_user=True để ALS tính lại user vector tức thì.
    """
    if _model is None:
        _load_model_from_disk()
    if _model is None:
        log.warning("ALS model not loaded. Run /ai/train first.")
        return []

    n_items = len(_item_map)
    if n_items == 0:
        return []

    # ── Bước 1: Lấy interaction HIỆN TẠI của user từ MongoDB (real-time) ──────
    db = get_db()
    from bson import ObjectId
    try:
        query_id = ObjectId(user_id)
    except Exception:
        query_id = user_id   # fallback: dùng string

    play_data: dict = {}   # item_col_idx -> tổng play_count
    async for doc in db.interactions.find(
        {"user_id": query_id},
        {"track_id": 1, "play_count": 1}
    ):
        track_id = str(doc["track_id"])
        i_idx = _item_map.get(track_id)
        if i_idx is not None:
            play_data[i_idx] = play_data.get(i_idx, 0.0) + float(doc.get("play_count", 1))

    if not play_data:
        log.info(f"[Folding-in] User {user_id}: không có interaction nào trong model → cold start.")
        return []

    # ── Bước 2: Build sparse row (1 × n_items) ────────────────────────────────
    indices = list(play_data.keys())
    values  = [play_data[i] for i in indices]
    user_row_raw = sp.csr_matrix(
        (values, ([0] * len(indices), indices)),
        shape=(1, n_items), dtype=np.float32,
    )

    # ── Bước 3: Áp BM25 weighting (giống lúc train) ───────────────────────────
    # Khi chỉ có 1 row: avgdl = dl, B mất tác dụng chuẩn hoá → saturation function
    # bm25(tf) = tf * (K1+1) / (K1 + tf)  — vẫn hợp lý cho folding-in
    user_row_bm25 = bm25_weight(user_row_raw, K1=BM25_K1, B=BM25_B).tocsr()

    liked_set = set(indices)
    req_n = min(top_n + len(liked_set) + 10, n_items - 1)

    # ── Bước 4: Folding-in — tính user vector mới, item_factors giữ nguyên ────
    try:
        ids_arr, _ = _model.recommend(
            0,                       # userid bị ignore khi recalculate_user=True
            user_row_bm25,
            N=req_n,
            recalculate_user=True,   # ← ALS giải user vector từ row vừa build
            filter_already_liked_items=False,
        )
        results = [
            _rev_item[int(i)]
            for i in ids_arr
            if int(i) not in liked_set and int(i) in _rev_item
        ]
        log.info(f"[Folding-in] User {user_id}: {len(play_data)} tracks → {len(results)} recs")
        return results[:top_n]

    except Exception as e:
        log.error(f"[Folding-in] Error for {user_id}: {e}")
        return []

