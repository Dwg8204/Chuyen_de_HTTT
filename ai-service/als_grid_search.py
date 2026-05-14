"""
als_grid_search.py — Grid Search ALS v5
  - Đọc từ JSON file (giống test.py), không cần MongoDB
  - Train/Test split dùng implicit.evaluation.train_test_split
  - BM25 weighting dùng implicit.nearest_neighbours.bm25_weight
  - Đánh giá dùng implicit.evaluation.ranking_metrics_at_k
  - Grid Search: factors, iterations, regularization, alpha(BM25_K1)
  - Giữ nguyên log NDCG, Precision, Recall (Recall tự tính thêm)

Cách chạy:
    cd "e:\\Kì 2 năm 4\\Chuyên đề\\Final\\ai-service"
    python als_grid_search.py
"""
import json, logging, math, os, time
from collections import defaultdict
from datetime import datetime, timezone
from itertools import product

import numpy as np
import scipy.sparse as sp
import implicit
import implicit.evaluation
from implicit.als import AlternatingLeastSquares
from implicit.nearest_neighbours import bm25_weight

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s │ %(levelname)s │ %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DATA_PATH  = os.path.join(BASE_DIR, "..", "data", "processed", "interactions.json")

# Ngưỡng lọc (giống test.py)
MIN_USER_UNIQUE_TRACKS = 0    # user có >= N bài khác nhau
MIN_ITEM_PLAYS         = 0    # item có tổng plays >= N

BM25_B = 0.8   # length normalization (cố định)

# ── Parameter Grid ──────────────────────────────────────────────────────────────
PARAM_GRID = {
    "factors":        [32, 64, 128],
    "iterations":     [20, 30, 50],
    "regularization": [0.01, 0.05, 0.1],
    "bm25_k1":        [1.0, 15.0, 40.0],   # BM25 K1 (= alpha cũ)
}


# ── Load & Filter data từ JSON ─────────────────────────────────────────────────
def load_data() -> sp.csr_matrix:
    log.info(f"📦 Đọc dữ liệu từ: {DATA_PATH}")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        interactions = json.load(f)
    log.info(f"   Raw interactions: {len(interactions):,}")

    # Đếm unique items/user và tổng plays/item
    user_unique: dict = defaultdict(set)
    item_total:  dict = defaultdict(float)
    for doc in interactions:
        uid = str(doc["_user_idx"])
        iid = str(doc["_track_idx"])
        cnt = float(doc.get("play_count", 1))
        user_unique[uid].add(iid)
        item_total[iid] += cnt

    active_users  = {u for u, s in user_unique.items() if len(s) >= MIN_USER_UNIQUE_TRACKS}
    popular_items = {i for i, c in item_total.items()  if c >= MIN_ITEM_PLAYS}
    log.info(f"   Users: {len(user_unique):,} → {len(active_users):,} (>={MIN_USER_UNIQUE_TRACKS} unique tracks)")
    log.info(f"   Items: {len(item_total):,} → {len(popular_items):,} (>={MIN_ITEM_PLAYS} total plays)")

    # Aggregate play_count theo (uid, iid) — đảm bảo không có duplicate trong matrix
    agg: dict = defaultdict(float)   # (uid_str, iid_str) -> total play_count
    user_map, item_map = {}, {}
    for doc in interactions:
        uid = str(doc["_user_idx"])
        iid = str(doc["_track_idx"])
        if uid not in active_users or iid not in popular_items: continue
        if uid not in user_map: user_map[uid] = len(user_map)
        if iid not in item_map: item_map[iid] = len(item_map)
        agg[(user_map[uid], item_map[iid])] += float(doc.get("play_count", 1))

    n_raw   = sum(1 for doc in interactions
                  if str(doc["_user_idx"]) in active_users
                  and str(doc["_track_idx"]) in popular_items)
    n_agg   = len(agg)
    if n_raw != n_agg:
        log.warning(f"   Phát hiện {n_raw - n_agg:,} dòng trùng lặp → đã cộng dồn!")
    else:
        log.info(f"   Không có duplicate — {n_agg:,} cặp (user, track) unique")

    # Build sparse matrix từ aggregated data
    rows_u = [k[0] for k in agg]; rows_i = [k[1] for k in agg]
    data   = [v for v in agg.values()]

    n_users = len(user_map)
    n_items = len(item_map)
    user_items = sp.csr_matrix((data, (rows_u, rows_i)), shape=(n_users, n_items), dtype=np.float32)
    nnz = user_items.nnz
    log.info(f"   Matrix: {n_users:,} users × {n_items:,} items | nnz={nnz:,}")
    log.info(f"   Density: {nnz / (n_users * n_items) * 100:.4f}%")
    return user_items


# ── Recall@K (bổ sung vì ranking_metrics_at_k không có recall) ────────────────
def compute_recall_at_k(model, train_ui, test_ui, k=10) -> float:
    """Tính Recall@K thủ công trên toàn bộ test users."""
    recalls = []
    n_users = train_ui.shape[0]
    for u in range(n_users):
        test_row = test_ui[u]
        if test_row.nnz == 0: continue
        gt = set(test_row.indices.tolist())
        # Gợi ý k bài chưa nghe trong train
        try:
            ids, _ = model.recommend(u, train_ui[u], N=k, filter_already_liked_items=True)
        except Exception:
            continue
        hit = len(set(ids.tolist()) & gt)
        recalls.append(hit / len(gt))
    return float(np.mean(recalls)) if recalls else 0.0


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    log.info("=" * 65)
    log.info("   ALS GRID SEARCH v5 — implicit.evaluation + BM25")
    log.info("=" * 65)

    # 1. Load data
    user_items = load_data()

    # 2. Train/Test split — dùng implicit.evaluation (giống test.py)
    log.info("✂️  Chia Train/Test với implicit.evaluation.train_test_split …")
    train_ui, test_ui = implicit.evaluation.train_test_split(
        user_items, train_percentage=0.8, random_state=42
    )
    log.info(f"   Train nnz: {train_ui.nnz:,} | Test nnz: {test_ui.nnz:,}")

    # 3. Grid Search
    combos = list(product(*PARAM_GRID.values()))
    keys   = list(PARAM_GRID.keys())
    total  = len(combos)
    log.info(f"\n🔍 Grid Search: {total} combinations")
    log.info(f"   {PARAM_GRID}\n")

    results = []; best_score = -1; best_entry = None

    for i, combo in enumerate(combos, 1):
        p = dict(zip(keys, combo))
        log.info(f"[{i:3d}/{total}] f={p['factors']} it={p['iterations']} "
                 f"reg={p['regularization']} K1={p['bm25_k1']}")

        # Áp dụng BM25 lên train set (giống test.py)
        train_bm25 = bm25_weight(train_ui, K1=p["bm25_k1"], B=BM25_B).tocsr()

        t0 = time.time()
        try:
            model = AlternatingLeastSquares(
                factors=p["factors"],
                iterations=p["iterations"],
                regularization=p["regularization"],
                random_state=42,
                num_threads=1,
            )
            model.fit(train_bm25, show_progress=False)
        except Exception as e:
            log.warning(f"   Training failed: {e}"); continue

        train_t = round(time.time() - t0, 2)

        # Đánh giá bằng implicit.evaluation (giống test.py)
        try:
            m10 = implicit.evaluation.ranking_metrics_at_k(
                model, train_ui, test_ui, K=10,
                show_progress=False, num_threads=1,
            )
            m20 = implicit.evaluation.ranking_metrics_at_k(
                model, train_ui, test_ui, K=20,
                show_progress=False, num_threads=1,
            )
            recall_10 = compute_recall_at_k(model, train_ui, test_ui, k=10)
            recall_20 = compute_recall_at_k(model, train_ui, test_ui, k=20)
        except Exception as e:
            log.warning(f"   Eval failed: {e}"); continue

        ndcg_10 = round(m10["ndcg"],      5)
        prec_10 = round(m10["precision"], 5)
        ndcg_20 = round(m20["ndcg"],      5)
        prec_20 = round(m20["precision"], 5)
        r10     = round(recall_10, 5)
        r20     = round(recall_20, 5)

        log.info(f"       NDCG@10={ndcg_10:.4f} | P@10={prec_10:.4f} | R@10={r10:.4f} | "
                 f"NDCG@20={ndcg_20:.4f} | {train_t}s")

        entry = {
            "params":  p,
            "metrics": {
                "ndcg_at_10":     ndcg_10,
                "precision_at_10":prec_10,
                "recall_at_10":   r10,
                "ndcg_at_20":     ndcg_20,
                "precision_at_20":prec_20,
                "recall_at_20":   r20,
            },
            "train_s": train_t,
        }
        results.append(entry)

        if ndcg_10 > best_score:
            best_score = ndcg_10; best_entry = entry
            log.info(f"       ⭐ New best NDCG@10 = {best_score:.5f}")

    # ── Report ─────────────────────────────────────────────────────────────────
    results.sort(key=lambda r: r["metrics"]["ndcg_at_10"], reverse=True)
    log.info("\n" + "=" * 75)
    log.info("   TOP 10 CONFIGURATIONS")
    log.info("=" * 75)
    log.info(f"{'#':<4}{'F':<6}{'I':<5}{'Reg':<7}{'K1':<8}{'NDCG@10':<10}{'P@10':<9}{'R@10':<9}{'NDCG@20'}")
    log.info("-" * 75)
    for rank, r in enumerate(results[:10], 1):
        p, m = r["params"], r["metrics"]
        log.info(f"{rank:<4}{p['factors']:<6}{p['iterations']:<5}{p['regularization']:<7}"
                 f"{p['bm25_k1']:<8}{m['ndcg_at_10']:<10.5f}{m['precision_at_10']:<9.5f}"
                 f"{m['recall_at_10']:<9.5f}{m['ndcg_at_20']:.5f}")

    if best_entry:
        bp, bm_ = best_entry["params"], best_entry["metrics"]
        log.info("\n" + "=" * 60)
        log.info("   🏆 BEST CONFIGURATION")
        log.info("=" * 60)
        log.info(f"   factors          = {bp['factors']}")
        log.info(f"   iterations       = {bp['iterations']}")
        log.info(f"   regularization   = {bp['regularization']}")
        log.info(f"   BM25 K1          = {bp['bm25_k1']}")
        log.info(f"   BM25 B           = {BM25_B} (fixed)")
        log.info("")
        log.info(f"   NDCG@10          = {bm_['ndcg_at_10']:.5f}")
        log.info(f"   Precision@10     = {bm_['precision_at_10']:.5f}")
        log.info(f"   Recall@10        = {bm_['recall_at_10']:.5f}")
        log.info(f"   NDCG@20          = {bm_['ndcg_at_20']:.5f}")
        log.info(f"   Precision@20     = {bm_['precision_at_20']:.5f}")
        log.info(f"   Recall@20        = {bm_['recall_at_20']:.5f}")
        log.info("=" * 60)
        log.info(f"""
✅ Cập nhật vào als_service.py:
    BM25_K1       = {bp['bm25_k1']}
    BM25_B        = {BM25_B}
    factors       = {bp['factors']}
    iterations    = {bp['iterations']}
    regularization= {bp['regularization']}
""")

    # ── Save JSON ───────────────────────────────────────────────────────────────
    out = {
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "config": {
            "MIN_USER_UNIQUE_TRACKS": MIN_USER_UNIQUE_TRACKS,
            "MIN_ITEM_PLAYS":         MIN_ITEM_PLAYS,
            "BM25_B":                 BM25_B,
            "param_grid":             PARAM_GRID,
            "matrix_shape": [int(user_items.shape[0]), int(user_items.shape[1])],
        },
        "best_params":  best_entry["params"]  if best_entry else None,
        "best_metrics": best_entry["metrics"] if best_entry else None,
        "all_results":  results,
    }
    out_path = os.path.join(BASE_DIR, "grid_search_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        import json as _json
        _json.dump(out, f, indent=2, ensure_ascii=False)
    log.info(f"💾 Saved → {out_path}")


if __name__ == "__main__":
    main()
