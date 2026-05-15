"""
Test standalone: doc JSON -> train ALS -> in ket qua
Chay: cd ai-service && python test_als_standalone.py
"""
import json, logging, os, time, pickle
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import scipy.sparse as sp
import implicit.evaluation
from implicit.als import AlternatingLeastSquares
from implicit.nearest_neighbours import bm25_weight

os.environ["OPENBLAS_NUM_THREADS"] = "1"

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "..", "data", "processed", "interactions.json")

FACTORS        = 64
ITERATIONS     = 20
REGULARIZATION = 0.1
BM25_K1        = 1.0
BM25_B         = 0.8
MIN_USER_UNIQUE_TRACKS = 30
MIN_ITEM_PLAYS         = 50

def main():
    log.info("=== ALS Standalone Test ===")
    t0 = time.time()

    # 1. Load data
    log.info(f"[1] Doc du lieu: {DATA_PATH}")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        interactions = json.load(f)
    log.info(f"[1] Raw interactions: {len(interactions):,}")

    # 2. Filter
    log.info("[2] Loc user/item...")
    user_unique = defaultdict(set)
    item_total  = defaultdict(float)
    for doc in interactions:
        uid = str(doc["_user_idx"])
        iid = str(doc["_track_idx"])
        cnt = float(doc.get("play_count", 1))
        user_unique[uid].add(iid)
        item_total[iid] += cnt

    active_users  = {u for u, s in user_unique.items() if len(s) >= MIN_USER_UNIQUE_TRACKS}
    popular_items = {i for i, c in item_total.items()  if c >= MIN_ITEM_PLAYS}
    log.info(f"[2] Users: {len(user_unique):,} -> {len(active_users):,}")
    log.info(f"[2] Items: {len(item_total):,} -> {len(popular_items):,}")

    # 3. Build matrix
    log.info("[3] Build sparse matrix...")
    agg = defaultdict(float)
    user_map, item_map = {}, {}
    for doc in interactions:
        uid = str(doc["_user_idx"])
        iid = str(doc["_track_idx"])
        if uid not in active_users or iid not in popular_items: continue
        if uid not in user_map: user_map[uid] = len(user_map)
        if iid not in item_map: item_map[iid] = len(item_map)
        agg[(user_map[uid], item_map[iid])] += float(doc.get("play_count", 1))

    rows_u = [k[0] for k in agg]
    rows_i = [k[1] for k in agg]
    data   = list(agg.values())
    n_users, n_items = len(user_map), len(item_map)
    user_items = sp.csr_matrix((data, (rows_u, rows_i)), shape=(n_users, n_items), dtype=np.float32)
    log.info(f"[3] Matrix: {n_users:,} users x {n_items:,} items | nnz={user_items.nnz:,}")

    # 4. Evaluation (80/20 split)
    log.info("[4] Evaluation (80/20 split)...")
    train_ui, test_ui = implicit.evaluation.train_test_split(
        user_items, train_percentage=0.8, random_state=42
    )
    train_bm25 = bm25_weight(train_ui, K1=BM25_K1, B=BM25_B).tocsr()
    eval_model = AlternatingLeastSquares(
        factors=FACTORS, iterations=ITERATIONS, regularization=REGULARIZATION,
        random_state=42, num_threads=1
    )
    log.info("[4] Fitting eval model...")
    eval_model.fit(train_bm25, show_progress=True)
    log.info("[4] Computing ranking metrics@10...")
    m10 = implicit.evaluation.ranking_metrics_at_k(
        eval_model, train_ui, test_ui, K=10, show_progress=False, num_threads=1
    )
    log.info("[4] Computing ranking metrics@20...")
    m20 = implicit.evaluation.ranking_metrics_at_k(
        eval_model, train_ui, test_ui, K=20, show_progress=False, num_threads=1
    )
    log.info("=" * 55)
    log.info("  KET QUA DANH GIA")
    log.info("=" * 55)
    log.info(f"  NDCG@10      = {m10['ndcg']:.5f}")
    log.info(f"  Precision@10 = {m10['precision']:.5f}")
    log.info(f"  NDCG@20      = {m20['ndcg']:.5f}")
    log.info(f"  Precision@20 = {m20['precision']:.5f}")
    log.info("=" * 55)

    # 5. Train final model on 100% data
    log.info("[5] Training final model on 100% data...")
    bm25_full = bm25_weight(user_items, K1=BM25_K1, B=BM25_B).tocsr()
    model = AlternatingLeastSquares(
        factors=FACTORS, iterations=ITERATIONS, regularization=REGULARIZATION,
        random_state=42, num_threads=1
    )
    model.fit(bm25_full, show_progress=True)

    # 6. Save model
    MODEL_PATH = os.path.join(BASE_DIR, "models", "als_model.pkl")
    os.makedirs(os.path.join(BASE_DIR, "models"), exist_ok=True)
    rev_item = {v: k for k, v in item_map.items()}
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({
            "model": model, "user_map": user_map,
            "item_map": item_map, "rev_item": rev_item,
        }, f)
    log.info(f"[6] Model saved to {MODEL_PATH}")
    log.info(f"Done in {round(time.time()-t0, 2)}s")

if __name__ == "__main__":
    main()
