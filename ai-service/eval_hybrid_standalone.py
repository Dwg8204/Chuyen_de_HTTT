"""
eval_hybrid_standalone.py
Đánh giá 3 mô hình: ALS (CF), Content-Based (CB), Hybrid
Chạy độc lập từ thư mục ai-service (không cần server):
  cd ai-service && python eval_hybrid_standalone.py
"""
import asyncio, json, logging, os, math, random, pickle, sys
from collections import defaultdict
from datetime import datetime, timezone

import numpy as np
import scipy.sparse as sp
from implicit.als import AlternatingLeastSquares
from implicit.nearest_neighbours import bm25_weight
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

os.environ["OPENBLAS_NUM_THREADS"] = "1"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

BASE  = os.path.dirname(os.path.abspath(__file__))
DATA  = os.path.join(BASE, "..", "data", "processed")
MODEL = os.path.join(BASE, "models", "als_model.pkl")

K_VALUES   = [10, 20]
MAX_EVAL   = 1_000    # Số user dùng để evaluate (tăng lên nếu muốn chính xác hơn)
HYBRID_CF  = 0.6      # Trọng số CF trong Hybrid
HYBRID_CB  = 0.4      # Trọng số CB trong Hybrid
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ── Metrics ────────────────────────────────────────────────────────────────────
def dcg(rels):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))

def ndcg_at_k(recs, gt, k):
    top = recs[:k]
    rels = [1.0 if t in gt else 0.0 for t in top]
    ideal = [1.0] * min(len(gt), k)
    d, i_d = dcg(rels), dcg(ideal)
    return d / i_d if i_d > 0 else 0.0

def recall_at_k(recs, gt, k):
    if not gt: return 0.0
    return len(set(recs[:k]) & gt) / len(gt)

def precision_at_k(recs, gt, k):
    if not recs: return 0.0
    return len(set(recs[:k]) & gt) / min(k, len(recs))


# ── Load data ──────────────────────────────────────────────────────────────────
def load_data():
    log.info("[Load] Reading interactions.json ...")
    with open(os.path.join(DATA, "interactions.json"), encoding="utf-8") as f:
        raw = json.load(f)
    log.info(f"[Load] {len(raw):,} interactions loaded")

    with open(os.path.join(DATA, "tracks.json"), encoding="utf-8") as f:
        tracks_raw = json.load(f)
    log.info(f"[Load] {len(tracks_raw):,} tracks loaded")

    # Build mapping: _track_idx -> content_vector
    cv_map = {}        # track_idx (int) -> np.array(7)
    tidx_to_idx = {}   # _track_idx (int) -> content list index
    for i, t in enumerate(tracks_raw):
        idx = t.get("_track_idx", i)
        cv  = t.get("content_vector")
        if cv and len(cv) == 7:
            cv_map[idx] = np.array(cv, dtype=np.float32)

    return raw, cv_map, len(tracks_raw)


def build_splits(raw, n_tracks):
    """80/20 split theo vị trí (giả sử thứ tự gần như ngẫu nhiên)."""
    n = len(raw)
    split = int(n * 0.8)
    train_raw = raw[:split]
    test_raw  = raw[split:]

    # user_idx -> set of track_idx (ground truth từ test)
    gt: dict = defaultdict(set)
    for d in test_raw:
        gt[d["_user_idx"]].add(d["_track_idx"])

    # user_idx -> {track_idx: play_count} (train)
    train: dict = defaultdict(dict)
    for d in train_raw:
        u, i, c = d["_user_idx"], d["_track_idx"], d["play_count"]
        train[u][i] = train[u].get(i, 0) + c

    # Chỉ evaluate users có dữ liệu trong cả train & test
    eval_users = [u for u in gt if u in train]
    random.shuffle(eval_users)
    eval_users = eval_users[:MAX_EVAL]
    log.info(f"[Split] Train nnz={len(train_raw):,} | Test nnz={len(test_raw):,} | Eval users: {len(eval_users):,}")
    return train, gt, eval_users


# ── ALS (CF) ───────────────────────────────────────────────────────────────────
def build_als_model(train, n_users, n_tracks):
    log.info("[ALS] Building ALS model on train set ...")
    rows, cols, data = [], [], []
    for u, items in train.items():
        for i, c in items.items():
            rows.append(u); cols.append(i); data.append(float(c))
    mat = sp.csr_matrix((data, (rows, cols)), shape=(n_users, n_tracks), dtype=np.float32)
    mat_bm25 = bm25_weight(mat, K1=1.0, B=0.8).tocsr()
    model = AlternatingLeastSquares(factors=64, iterations=20, regularization=0.1,
                                    random_state=42, num_threads=1)
    model.fit(mat_bm25, show_progress=True)
    return model, mat


def als_recommend(model, mat, u_idx, liked_set, n_items, top_n=20):
    row = mat[u_idx]
    row_bm25 = bm25_weight(sp.csr_matrix(row), K1=1.0, B=0.8).tocsr()
    req_n = min(top_n + len(liked_set) + 5, n_items - 1)
    try:
        ids, _ = model.recommend(u_idx, row_bm25, N=req_n,
                                  recalculate_user=True,
                                  filter_already_liked_items=False)
        return [int(i) for i in ids if int(i) not in liked_set][:top_n]
    except Exception as e:
        log.warning(f"ALS recommend error u={u_idx}: {e}")
        return []


# ── Content-Based (CB) ─────────────────────────────────────────────────────────
def build_cb_index(cv_map, n_tracks):
    """Build L2-normalized content vector matrix."""
    log.info("[CB] Building content vector index ...")
    n_feat = 7
    mat = np.zeros((n_tracks, n_feat), dtype=np.float32)
    for idx, vec in cv_map.items():
        if idx < n_tracks:
            mat[idx] = vec
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def cb_recommend(cb_mat, train_items: dict, liked_set: set, n_tracks: int, top_n=20):
    if not train_items:
        return []
    # Aggregate cosine similarities từ top-5 bài nghe nhiều nhất
    agg = np.zeros(n_tracks, dtype=np.float32)
    src_idxs = sorted(train_items.keys(), key=lambda i: train_items[i], reverse=True)[:5]
    for idx in src_idxs:
        if idx < n_tracks:
            agg += cb_mat @ cb_mat[idx]
    # Loại bỏ bài đã nghe
    for i in liked_set:
        if i < n_tracks:
            agg[i] = -999.0
    return list(np.argsort(-agg)[:top_n])


# ── Hybrid ─────────────────────────────────────────────────────────────────────
def hybrid_recommend(model, mat, cb_mat, train_items, liked_set, n_tracks, top_n=20):
    cf_recs  = als_recommend(model, mat, list(train_items.keys())[0] if train_items else 0,
                              liked_set, n_tracks, top_n * 2)
    cb_recs  = cb_recommend(cb_mat, train_items, liked_set, n_tracks, top_n * 2)

    cf_score = {i: (top_n * 2 - rank) * HYBRID_CF for rank, i in enumerate(cf_recs)}
    cb_score = {i: (top_n * 2 - rank) * HYBRID_CB for rank, i in enumerate(cb_recs)}

    all_items = set(cf_score) | set(cb_score)
    combined  = sorted(all_items, key=lambda i: cf_score.get(i, 0) + cb_score.get(i, 0), reverse=True)
    return [i for i in combined if i not in liked_set][:top_n]


# ── Evaluate ───────────────────────────────────────────────────────────────────
def evaluate_model(name, rec_fn, eval_users, train, gt, n_tracks, rec_pool):
    log.info(f"[Eval] {name} on {len(eval_users)} users ...")
    ndcg, rec, prec = {k: [] for k in K_VALUES}, {k: [] for k in K_VALUES}, {k: [] for k in K_VALUES}

    for u in eval_users:
        liked_set = set(train[u].keys())
        gt_set    = gt[u]
        if not gt_set: continue

        recs = rec_fn(u, train[u], liked_set)
        if not recs: continue

        for k in K_VALUES:
            ndcg[k].append(ndcg_at_k(recs, gt_set, k))
            rec[k].append(recall_at_k(recs, gt_set, k))
            prec[k].append(precision_at_k(recs, gt_set, k))
        rec_pool.update(recs)

    n_eval = len(ndcg[K_VALUES[0]])
    if n_eval == 0:
        return {"model": name, "error": "no results"}

    result = {"model": name, "users_evaluated": n_eval}
    for k in K_VALUES:
        result[f"ndcg@{k}"]      = round(float(np.mean(ndcg[k])), 5)
        result[f"recall@{k}"]    = round(float(np.mean(rec[k])),  5)
        result[f"precision@{k}"] = round(float(np.mean(prec[k])), 5)
    return result


# ── Report ─────────────────────────────────────────────────────────────────────
def print_report(results, n_tracks, rec_pools):
    BOLD = "\033[1m"; RESET = "\033[0m"; GREEN = "\033[92m"
    log.info("\n" + "=" * 75)
    log.info(f"{BOLD}   EVALUATION RESULTS   {RESET}")
    log.info("=" * 75)
    header = f"{'Model':<35} {'NDCG@10':>8} {'R@10':>8} {'P@10':>8} {'NDCG@20':>8} {'R@20':>8} {'P@20':>8} {'Cov':>6}"
    log.info(header)
    log.info("-" * 75)
    for r, pool in zip(results, rec_pools):
        cov = len(pool) / n_tracks if n_tracks else 0
        log.info(
            f"{r['model']:<35} "
            f"{r.get('ndcg@10', 0):>8.4f} "
            f"{r.get('recall@10', 0):>8.4f} "
            f"{r.get('precision@10', 0):>8.4f} "
            f"{r.get('ndcg@20', 0):>8.4f} "
            f"{r.get('recall@20', 0):>8.4f} "
            f"{r.get('precision@20', 0):>8.4f} "
            f"{cov:>6.3f}"
        )
    log.info("=" * 75)

    # Save chart
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")
    metrics_labels = ["NDCG@10", "Recall@10", "Precision@10", "NDCG@20", "Recall@20", "Precision@20"]
    x = np.arange(len(metrics_labels))
    width = 0.25
    colors = ["#1DB954", "#6c63ff", "#f0a500"]
    for j, (r, c) in enumerate(zip(results, colors)):
        vals = [r.get("ndcg@10", 0), r.get("recall@10", 0), r.get("precision@10", 0),
                r.get("ndcg@20", 0), r.get("recall@20", 0), r.get("precision@20", 0)]
        bars = ax.bar(x + j * width, vals, width, label=r["model"], color=c, alpha=0.85)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                    f"{v:.3f}", ha="center", color="white", fontsize=7)

    ax.set_xticks(x + width)
    ax.set_xticklabels(metrics_labels, color="white", fontsize=9)
    ax.tick_params(colors="white")
    ax.legend(facecolor="#2a2a4a", labelcolor="white", fontsize=9)
    ax.set_title("Model Evaluation Comparison", color="white", fontsize=13, fontweight="bold")
    for sp in ax.spines.values(): sp.set_edgecolor("#444")
    plt.tight_layout()
    out = os.path.join(BASE, "evaluation_results", "comparison.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    plt.savefig(out, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    log.info(f"[Chart] Saved to {out}")
    return out


def main():
    raw, cv_map, n_tracks_total = load_data()
    n_users = max(d["_user_idx"] for d in raw) + 1
    n_tracks = max(d["_track_idx"] for d in raw) + 1
    log.info(f"[Info] n_users={n_users:,} | n_tracks_total={n_tracks_total:,} | n_tracks_interacted={n_tracks:,}")

    train, gt, eval_users = build_splits(raw, n_tracks)

    # Build models
    als_model, als_mat = build_als_model(train, n_users, n_tracks)
    cb_mat = build_cb_index(cv_map, n_tracks)

    # Evaluate
    cf_pool, cb_pool, hy_pool = set(), set(), set()

    cf_result = evaluate_model(
        "Collaborative Filtering (ALS)",
        lambda u, items, liked: als_recommend(als_model, als_mat, u, liked, n_tracks, 20),
        eval_users, train, gt, n_tracks, cf_pool
    )

    cb_result = evaluate_model(
        "Content-Based (Cosine Sim)",
        lambda u, items, liked: cb_recommend(cb_mat, items, liked, n_tracks, 20),
        eval_users, train, gt, n_tracks, cb_pool
    )

    hy_result = evaluate_model(
        "Hybrid (0.6·CF + 0.4·CB)",
        lambda u, items, liked: hybrid_recommend(als_model, als_mat, cb_mat, items, liked, n_tracks, 20),
        eval_users, train, gt, n_tracks, hy_pool
    )

    results = [cf_result, cb_result, hy_result]
    pools   = [cf_pool, cb_pool, hy_pool]

    print_report(results, n_tracks_total, pools)

    # Save JSON
    out_json = os.path.join(BASE, "evaluation_results", "eval_results.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "eval_users": len(eval_users),
            "results": results,
        }, f, ensure_ascii=False, indent=2)
    log.info(f"[Done] Results saved to {out_json}")


if __name__ == "__main__":
    main()
