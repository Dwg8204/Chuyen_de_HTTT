"""
eval_service.py - Đánh giá CF và CB models: NDCG@10, Recall@K, Precision@K, Coverage
"""
import logging, os, math
from datetime import datetime, timezone
from collections import defaultdict
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from app.database import get_db
from app.services import als_service

log = logging.getLogger(__name__)
EVAL_DIR = "evaluation_results"
os.makedirs(EVAL_DIR, exist_ok=True)


# ── Metric helpers ─────────────────────────────────────────────────────────────
def _dcg(relevances):
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))

def _ndcg_at_k(recommended, ground_truth, k=10):
    top_k = recommended[:k]
    relevances = [1.0 if tid in ground_truth else 0.0 for tid in top_k]
    dcg   = _dcg(relevances)
    ideal = [1.0] * min(len(ground_truth), k)
    idcg  = _dcg(ideal)
    return dcg / idcg if idcg > 0 else 0.0

def _recall_at_k(recommended, ground_truth, k):
    if not ground_truth: return 0.0
    return len(set(recommended[:k]) & ground_truth) / len(ground_truth)

def _precision_at_k(recommended, ground_truth, k):
    if not recommended: return 0.0
    return len(set(recommended[:k]) & ground_truth) / min(k, len(recommended))


# ── Shared data loader ─────────────────────────────────────────────────────────
async def _load_splits(max_users: int = 500):
    """Load interactions từ MongoDB, chia 80/20 theo thời gian."""
    db = get_db()
    all_docs = []
    async for doc in db.interactions.find(
        {}, {"user_id": 1, "track_id": 1, "last_played": 1}
    ):
        all_docs.append(doc)

    if not all_docs:
        return None, None, None, None

    all_docs.sort(key=lambda d: d.get("last_played", datetime.min))
    split_idx  = int(len(all_docs) * 0.8)
    train_docs = all_docs[:split_idx]
    test_docs  = all_docs[split_idx:]

    ground_truth: dict = defaultdict(set)
    for doc in test_docs:
        ground_truth[str(doc["user_id"])].add(str(doc["track_id"]))

    train_map: dict = defaultdict(list)
    for doc in train_docs:
        train_map[str(doc["user_id"])].append(str(doc["track_id"]))

    train_users = set(train_map.keys())
    eval_users  = [u for u in ground_truth if u in train_users][:max_users]

    all_track_ids = set()
    async for doc in db.tracks.find({}, {"_id": 1}):
        all_track_ids.add(str(doc["_id"]))

    return train_map, ground_truth, eval_users, all_track_ids


# ── CF Evaluation ─────────────────────────────────────────────────────────────
async def run_evaluation(k_values=[10, 20]) -> dict:
    """Đánh giá Collaborative Filtering (ALS)."""
    train_map, ground_truth, eval_users, all_track_ids = await _load_splits(500)
    if eval_users is None:
        return {"error": "No interaction data"}
    if not eval_users:
        return {"error": "No overlapping users between train/test splits"}

    log.info(f"CF Evaluation on {len(eval_users)} users …")
    rec_pool, ndcg_scores = set(), []
    recall_scores = {k: [] for k in k_values}
    prec_scores   = {k: [] for k in k_values}

    for uid in eval_users:
        recs = await als_service.get_cf_recommendations(uid, top_n=max(k_values))
        if not recs: continue
        gt = ground_truth[uid]
        ndcg_scores.append(_ndcg_at_k(recs, gt, 10))
        for k in k_values:
            recall_scores[k].append(_recall_at_k(recs, gt, k))
            prec_scores[k].append(_precision_at_k(recs, gt, k))
        rec_pool.update(recs)

    if not ndcg_scores:
        return {"error": "No CF recommendations – please run ALS training first"}

    coverage = len(rec_pool) / len(all_track_ids) if all_track_ids else 0.0
    results = {
        "model": "Collaborative Filtering (ALS)",
        "users_evaluated": len(ndcg_scores),
        "ndcg_at_10": round(float(np.mean(ndcg_scores)), 4),
        "coverage":   round(coverage, 4),
    }
    for k in k_values:
        results[f"recall_at_{k}"]    = round(float(np.mean(recall_scores[k])), 4)
        results[f"precision_at_{k}"] = round(float(np.mean(prec_scores[k])), 4)

    results["chart_path"] = _generate_chart(results, "cf")
    log.info(f"CF results: {results}")
    return results


# ── CB Evaluation ─────────────────────────────────────────────────────────────
async def run_cb_evaluation(k_values=[10, 20]) -> dict:
    """
    Đánh giá Content-Based Filtering (Cosine Similarity).
    Logic: với mỗi user trong test split, lấy train_tracks → aggregate CB scores
    → rank → so với ground_truth.
    """
    from app.services.cb_service import _ensure_cache, _track_ids, _vectors

    train_map, ground_truth, eval_users, all_track_ids = await _load_splits(300)
    if eval_users is None:
        return {"error": "No interaction data"}
    if not eval_users:
        return {"error": "No overlapping users between train/test splits"}

    await _ensure_cache()
    if _vectors is None or not _track_ids:
        return {"error": "Content vectors not loaded. Make sure tracks have content_vector in MongoDB."}

    log.info(f"CB Evaluation on {len(eval_users)} users …")
    tid_to_idx = {tid: i for i, tid in enumerate(_track_ids)}
    vectors    = _vectors   # shape (n_tracks, n_features), L2-normalized

    rec_pool, ndcg_scores = set(), []
    recall_scores = {k: [] for k in k_values}
    prec_scores   = {k: [] for k in k_values}

    for uid in eval_users:
        train_tracks = train_map.get(uid, [])
        gt           = ground_truth[uid]
        if not train_tracks or not gt:
            continue

        agg = np.zeros(len(_track_ids), dtype=np.float32)
        exclude = set(train_tracks)
        for src_tid in train_tracks[:10]:
            idx = tid_to_idx.get(src_tid)
            if idx is None: continue
            agg += vectors @ vectors[idx]

        ranked = sorted(
            [(i, float(agg[i])) for i in range(len(_track_ids))
             if _track_ids[i] not in exclude],
            key=lambda x: x[1], reverse=True
        )
        recs = [_track_ids[i] for i, _ in ranked[:max(k_values)]]
        if not recs: continue

        ndcg_scores.append(_ndcg_at_k(recs, gt, 10))
        for k in k_values:
            recall_scores[k].append(_recall_at_k(recs, gt, k))
            prec_scores[k].append(_precision_at_k(recs, gt, k))
        rec_pool.update(recs)

    if not ndcg_scores:
        return {"error": "No CB results. Check content_vector data in tracks collection."}

    coverage = len(rec_pool) / len(all_track_ids) if all_track_ids else 0.0
    results = {
        "model": "Content-Based Filtering (Cosine Similarity)",
        "users_evaluated": len(ndcg_scores),
        "ndcg_at_10": round(float(np.mean(ndcg_scores)), 4),
        "coverage":   round(coverage, 4),
    }
    for k in k_values:
        results[f"recall_at_{k}"]    = round(float(np.mean(recall_scores[k])), 4)
        results[f"precision_at_{k}"] = round(float(np.mean(prec_scores[k])), 4)

    results["chart_path"] = _generate_chart(results, "cb")
    log.info(f"CB results: {results}")
    return results


# ── Chart ─────────────────────────────────────────────────────────────────────
def _generate_chart(results: dict, prefix: str = "cf") -> str:
    is_cb  = prefix == "cb"
    c1     = "#6c63ff" if is_cb else "#1DB954"
    c2     = "#5a52d5" if is_cb else "#1aa34a"
    c3     = "#4a43b8" if is_cb else "#158f40"
    label  = "Content-Based" if is_cb else "Collaborative Filtering"

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.patch.set_facecolor("#1a1a2e")
    fig.suptitle(f"Evaluation — {label}", color="white", fontsize=13, fontweight="bold")

    metrics = ["NDCG@10", "Recall@10", "Recall@20", "Prec@10", "Prec@20"]
    values  = [
        results.get("ndcg_at_10", 0),
        results.get("recall_at_10", 0),
        results.get("recall_at_20", 0),
        results.get("precision_at_10", 0),
        results.get("precision_at_20", 0),
    ]

    ax1 = axes[0]
    bars = ax1.bar(metrics, values, color=[c1, c2, c3, c2, c3], width=0.6)
    ax1.set_ylim(0, max(max(values) * 1.35, 0.05))
    ax1.set_facecolor("#16213e")
    ax1.tick_params(colors="white", labelsize=8)
    ax1.set_title("Ranking Metrics", color="white")
    for sp in ax1.spines.values(): sp.set_edgecolor("#444")
    for bar, val in zip(bars, values):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                 f"{val:.3f}", ha="center", color="white", fontsize=8)

    ax2 = axes[1]
    cov = results.get("coverage", 0)
    ax2.pie([cov, max(0, 1-cov)],
            labels=[f"Covered\n{cov*100:.1f}%", "Not covered"],
            colors=[c1, "#2a2a4a"], startangle=90,
            textprops={"color": "white", "fontsize": 9})
    ax2.set_title("Catalog Coverage", color="white")

    ax3 = axes[2]
    ax3.axis("off")
    summary = (
        f"{'CB' if is_cb else 'CF'} Model Summary\n\n"
        f"Users evaluated: {results.get('users_evaluated', 0)}\n\n"
        f"NDCG@10:      {results.get('ndcg_at_10', 0):.4f}\n"
        f"Recall@10:    {results.get('recall_at_10', 0):.4f}\n"
        f"Recall@20:    {results.get('recall_at_20', 0):.4f}\n"
        f"Precision@10: {results.get('precision_at_10', 0):.4f}\n"
        f"Precision@20: {results.get('precision_at_20', 0):.4f}\n"
        f"Coverage:     {results.get('coverage', 0):.4f}"
    )
    ax3.text(0.05, 0.95, summary, transform=ax3.transAxes,
             color="white", fontsize=9, va="top", fontfamily="monospace",
             bbox=dict(boxstyle="round", facecolor="#2a2a4a", alpha=0.8))

    plt.tight_layout()
    ts   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(EVAL_DIR, f"{prefix}_metrics_{ts}.png")
    plt.savefig(path, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    return path
