"""
eval_cb_hybrid.py
Đánh giá Content-Based (CB) và Hybrid (CB + ALS) models
Dùng thư viện:
  - sklearn.model_selection.train_test_split (chia tập dữ liệu)
  - sklearn.metrics.ndcg_score (NDCG@K)
  - sklearn.metrics.precision_score, recall_score (Precision@K, Recall@K)

Chạy: cd ai-service && python eval_cb_hybrid.py
"""
import json, logging, os, sys, random, time
from collections import defaultdict

import numpy as np
import scipy.sparse as sp

from sklearn.model_selection import train_test_split
from sklearn.metrics import ndcg_score, precision_score, recall_score

from implicit.als import AlternatingLeastSquares
from implicit.nearest_neighbours import bm25_weight

os.environ["OPENBLAS_NUM_THREADS"] = "1"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE  = os.path.dirname(os.path.abspath(__file__))
DATA  = os.path.join(BASE, "..", "data", "processed")

# ── Hyper-params ────────────────────────────────────────────────────────────────
K            = 10        # cutoff
MAX_USERS    = 500       # số user evaluate (giảm nếu máy yếu)
ALS_FACTORS  = 64
ALS_ITERS    = 20
ALS_REG      = 0.1
BM25_K1      = 1.0
BM25_B       = 0.8
CF_WEIGHT    = 0.6       # trọng số CF trong Hybrid
CB_WEIGHT    = 0.4       # trọng số CB trong Hybrid
SEED         = 42
random.seed(SEED); np.random.seed(SEED)


# ════════════════════════════════════════════════════════════════
# 1. LOAD DATA
# ════════════════════════════════════════════════════════════════
def load():
    log.info("[1] Loading interactions.json ...")
    with open(os.path.join(DATA, "interactions.json"), encoding="utf-8") as f:
        ints = json.load(f)
    log.info(f"    {len(ints):,} interactions")

    log.info("[1] Loading tracks.json ...")
    with open(os.path.join(DATA, "tracks.json"), encoding="utf-8") as f:
        tracks = json.load(f)
    log.info(f"    {len(tracks):,} tracks")

    # content_vector: track_idx = position in JSON array (same as _track_idx in interactions)
    cv_map = {}
    for idx, t in enumerate(tracks):
        cv = t.get("content_vector")
        if cv and len(cv) >= 7:   # hỗ trợ 7D (cũ) lẫn 12D (mới)
            cv_map[idx] = np.array(cv, dtype=np.float32)

    n_users  = max(d["_user_idx"]  for d in ints) + 1
    n_tracks = max(d["_track_idx"] for d in ints) + 1
    log.info(f"    n_users={n_users:,} | n_tracks={n_tracks:,} | cv_items={len(cv_map):,}")
    return ints, cv_map, n_users, n_tracks


# ════════════════════════════════════════════════════════════════
# 2. TRAIN/TEST SPLIT  (dùng sklearn.model_selection.train_test_split)
# ════════════════════════════════════════════════════════════════
def split(ints):
    log.info("[2] Splitting 80/20 via sklearn.train_test_split ...")
    train_raw, test_raw = train_test_split(ints, test_size=0.2, random_state=SEED, shuffle=True)
    log.info(f"    Train={len(train_raw):,} | Test={len(test_raw):,}")

    # train: user_idx -> {track_idx: total_play_count}
    train_map = defaultdict(dict)
    for d in train_raw:
        u, i, c = d["_user_idx"], d["_track_idx"], d["play_count"]
        train_map[u][i] = train_map[u].get(i, 0) + c

    # ground_truth: user_idx -> set of track_idx
    gt = defaultdict(set)
    for d in test_raw:
        gt[d["_user_idx"]].add(d["_track_idx"])

    # Lấy users có dữ liệu trong cả train lẫn test
    eval_users = [u for u in gt if u in train_map and len(gt[u]) > 0]
    random.shuffle(eval_users)
    eval_users = eval_users[:MAX_USERS]
    log.info(f"    Eval users: {len(eval_users):,}")
    return train_map, gt, eval_users


# ════════════════════════════════════════════════════════════════
# 3. BUILD MODELS
# ════════════════════════════════════════════════════════════════
def build_als(train_map, n_users, n_tracks):
    log.info("[3] Building ALS model on train set ...")
    rows, cols, data = [], [], []
    for u, items in train_map.items():
        for i, c in items.items():
            rows.append(u); cols.append(i); data.append(float(c))
    mat = sp.csr_matrix((data, (rows, cols)), shape=(n_users, n_tracks), dtype=np.float32)
    mat_bm25 = bm25_weight(mat, K1=BM25_K1, B=BM25_B).tocsr()
    model = AlternatingLeastSquares(
        factors=ALS_FACTORS, iterations=ALS_ITERS,
        regularization=ALS_REG, random_state=SEED, num_threads=1
    )
    model.fit(mat_bm25, show_progress=True)
    log.info("    ALS training done.")
    return model, mat


def build_cb_matrix(cv_map, n_tracks):
    log.info("[3] Building Content-Based matrix ...")
    # Đọc số chiều thực tế từ cv_map (tránh hard-code)
    n_feat = len(next(iter(cv_map.values()))) if cv_map else 7
    mat = np.zeros((n_tracks, n_feat), dtype=np.float32)
    for idx, vec in cv_map.items():
        if idx < n_tracks:
            mat[idx] = vec
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = mat / norms
    log.info(f"    CB matrix: {mat.shape} | dim={n_feat}")
    return mat


# ════════════════════════════════════════════════════════════════
# 4. RECOMMENDATION FUNCTIONS
# ════════════════════════════════════════════════════════════════
def cf_scores(als_model, mat_bm25, u_idx, n_tracks):
    """Trả về score array (n_tracks,) theo ALS (folding-in)."""
    row = mat_bm25[u_idx]
    row_bm25 = bm25_weight(sp.csr_matrix(row), K1=BM25_K1, B=BM25_B).tocsr()
    try:
        item_factors = als_model.item_factors          # (n_tracks, factors)
        # Giải user vector bằng closed-form (folding-in)
        YtY = item_factors.T @ item_factors
        confidence = row_bm25.toarray().flatten()
        # Chỉ dùng items có confidence > 0
        Yt_Cu = item_factors.T @ (confidence * item_factors).T.sum(axis=1)
        # Giải (YtY + λI) xu = YtCupu
        A = YtY + ALS_REG * np.eye(ALS_FACTORS, dtype=np.float32)
        b = item_factors.T @ (confidence * 1.0)       # simplified
        user_vec = np.linalg.solve(A.T @ A, A.T @ b)
        scores = item_factors @ user_vec
        return scores.astype(np.float32)
    except Exception:
        # Fallback: lấy trực tiếp từ model
        try:
            ids, sc = als_model.recommend(u_idx, mat_bm25[u_idx], N=n_tracks,
                                           recalculate_user=True,
                                           filter_already_liked_items=False)
            score_arr = np.zeros(n_tracks, dtype=np.float32)
            for i, s in zip(ids, sc):
                if int(i) < n_tracks:
                    score_arr[int(i)] = float(s)
            return score_arr
        except Exception:
            return np.zeros(n_tracks, dtype=np.float32)


def cb_scores_for_user(cb_mat, train_items: dict, n_tracks):
    """Aggregate cosine similarity scores từ top bài đã nghe."""
    agg = np.zeros(n_tracks, dtype=np.float32)
    # Top-5 bài nghe nhiều nhất
    src = sorted(train_items.keys(), key=lambda i: train_items[i], reverse=True)[:5]
    for idx in src:
        if idx < n_tracks:
            agg += cb_mat @ cb_mat[idx]
    return agg


# ════════════════════════════════════════════════════════════════
# 5. METRIC HELPERS  (dùng sklearn)
# ════════════════════════════════════════════════════════════════
def metrics_at_k(score_arr, gt_set, liked_set, n_tracks, k=10):
    """
    Tính NDCG@K, Precision@K, Recall@K dùng sklearn.
    score_arr: (n_tracks,) float  — điểm dự đoán
    gt_set   : set of track_idx  — ground truth
    liked_set: set of track_idx  — đã nghe (lọc khỏi recommendations)
    """
    # Mask bài đã nghe (không recommend)
    score_arr = score_arr.copy()
    for i in liked_set:
        if i < n_tracks:
            score_arr[i] = -1e9

    # Ground truth binary array
    y_true = np.zeros(n_tracks, dtype=np.int32)
    for i in gt_set:
        if i < n_tracks:
            y_true[i] = 1

    # Nếu không có ground truth → bỏ qua
    if y_true.sum() == 0:
        return None

    # ── NDCG@K  (sklearn.metrics.ndcg_score) ──────────────────
    # ndcg_score expects shape (1, n_samples)
    ndcg = ndcg_score(y_true.reshape(1, -1), score_arr.reshape(1, -1), k=k)

    # ── Precision@K & Recall@K ────────────────────────────────
    # Tạo binary prediction: 1 cho top-K items
    top_k_idx = np.argpartition(score_arr, -k)[-k:]   # top-K indices (unordered)
    y_pred = np.zeros(n_tracks, dtype=np.int32)
    y_pred[top_k_idx] = 1

    # sklearn.metrics.precision_score / recall_score
    prec = precision_score(y_true, y_pred, zero_division=0)
    rec  = recall_score(y_true, y_pred, zero_division=0)

    return {"ndcg": ndcg, "precision": prec, "recall": rec}


# ════════════════════════════════════════════════════════════════
# 6. EVALUATION LOOP
# ════════════════════════════════════════════════════════════════
def evaluate(name, score_fn, eval_users, train_map, gt, n_tracks):
    log.info(f"\n[Eval] {name} — {len(eval_users)} users ...")
    ndcg_list, prec_list, rec_list = [], [], []

    for cnt, u in enumerate(eval_users):
        if (cnt + 1) % 100 == 0:
            log.info(f"  Progress: {cnt+1}/{len(eval_users)}")
        liked_set = set(train_map[u].keys())
        gt_set    = gt[u]
        if not gt_set or not liked_set:
            continue

        scores = score_fn(u, train_map[u])
        if scores is None:
            continue

        m = metrics_at_k(scores, gt_set, liked_set, n_tracks, k=K)
        if m is None:
            continue

        ndcg_list.append(m["ndcg"])
        prec_list.append(m["precision"])
        rec_list.append(m["recall"])

    n = len(ndcg_list)
    if n == 0:
        return {"model": name, "error": "no results"}

    result = {
        "model":            name,
        "users_evaluated":  n,
        f"ndcg@{K}":        round(float(np.mean(ndcg_list)),  5),
        f"precision@{K}":   round(float(np.mean(prec_list)),  5),
        f"recall@{K}":      round(float(np.mean(rec_list)),   5),
    }
    log.info(
        f"  → NDCG@{K}={result[f'ndcg@{K}']:.5f} | "
        f"P@{K}={result[f'precision@{K}']:.5f} | "
        f"R@{K}={result[f'recall@{K}']:.5f} | "
        f"n={n}"
    )
    return result


# ════════════════════════════════════════════════════════════════
# 7. MAIN
# ════════════════════════════════════════════════════════════════
def main():
    t0 = time.time()
    ints, cv_map, n_users, n_tracks = load()
    train_map, gt, eval_users       = split(ints)

    # Build models
    als_model, als_mat = build_als(train_map, n_users, n_tracks)
    cb_mat             = build_cb_matrix(cv_map, n_tracks)

    # BM25-weighted train matrix (dùng cho ALS folding-in)
    rows, cols, data = [], [], []
    for u, items in train_map.items():
        for i, c in items.items():
            rows.append(u); cols.append(i); data.append(float(c))
    mat_raw  = sp.csr_matrix((data, (rows, cols)), shape=(n_users, n_tracks), dtype=np.float32)
    mat_bm25 = bm25_weight(mat_raw, K1=BM25_K1, B=BM25_B).tocsr()

    # ── CB Evaluation ─────────────────────────────────────────
    cb_result = evaluate(
        f"Content-Based (Cosine Sim, K={K})",
        lambda u, items: cb_scores_for_user(cb_mat, items, n_tracks),
        eval_users, train_map, gt, n_tracks,
    )

    # ── Hybrid Evaluation ─────────────────────────────────────
    def hybrid_score_fn(u, items):
        cf = cf_scores(als_model, mat_bm25, u, n_tracks)
        cb = cb_scores_for_user(cb_mat, items, n_tracks)

        # Normalize về [0,1] trước khi kết hợp
        def norm(arr):
            mn, mx = arr.min(), arr.max()
            return (arr - mn) / (mx - mn + 1e-8)

        return CF_WEIGHT * norm(cf) + CB_WEIGHT * norm(cb)

    hy_result = evaluate(
        f"Hybrid ({CF_WEIGHT}·CF + {CB_WEIGHT}·CB, K={K})",
        hybrid_score_fn,
        eval_users, train_map, gt, n_tracks,
    )

    # ── Print Summary ─────────────────────────────────────────
    print("\n" + "=" * 65)
    print(f"  {'Model':<38} {'NDCG@10':>8} {'P@10':>8} {'R@10':>8}")
    print("=" * 65)
    for r in [cb_result, hy_result]:
        if "error" in r:
            print(f"  {r['model']:<38}  ERROR: {r['error']}")
        else:
            print(
                f"  {r['model']:<38} "
                f"{r.get(f'ndcg@{K}', 0):>8.5f} "
                f"{r.get(f'precision@{K}', 0):>8.5f} "
                f"{r.get(f'recall@{K}', 0):>8.5f}"
            )
    print("=" * 65)
    print(f"  Completed in {round(time.time() - t0, 1)}s\n")

    # Lưu JSON
    import json
    out = os.path.join(BASE, "evaluation_results", "cb_hybrid_eval.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"cb": cb_result, "hybrid": hy_result,
                   "k": K, "eval_users": len(eval_users)}, f, indent=2)
    log.info(f"[Done] Results saved to {out}")


if __name__ == "__main__":
    main()
