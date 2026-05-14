"""
als_grid_search.py — Grid Search ALS v4
  - Diagnostics: kiểm tra data join, item overlap train/test
  - BM25 weighting thay log weighting
  - Per-User 80/20 split chuẩn
"""
import asyncio, json, logging, math, os, time
from collections import defaultdict
from datetime import datetime, timezone
from itertools import product

import numpy as np
import scipy.sparse as sp
from dotenv import load_dotenv
from implicit.als import AlternatingLeastSquares
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s │ %(levelname)s │ %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
MONGO_URI              = os.getenv("MONGODB_URI", "mongodb://localhost:27017/musicrec")
MIN_USER_UNIQUE_TRACKS = 20    # lọc user có < N bài KHÁC NHAU
MIN_ITEM_PLAYS         = 50    # lọc track có tổng plays < N
MIN_EVAL_TEST_ITEMS    = 5     # user phải có >= N bài trong test
K_VALUES               = [10, 20]
MAX_EVAL_USERS         = 1000

# BM25 params
BM25_K1 = 100.0   # saturation — cao hơn = ít saturation hơn
BM25_B  = 0.8     # length normalization

PARAM_GRID = {
    "factors":        [32, 64, 128, 256],
    "iterations":     [20, 30, 50],
    "regularization": [0.01, 0.05, 0.1, 0.5],
    "alpha":          [1.0, 15.0, 40.0, 100.0],
}


# ── Metrics ────────────────────────────────────────────────────────────────────
def _dcg(rel): return sum(r / math.log2(i+2) for i,r in enumerate(rel))
def _ndcg(recs, gt, k=10):
    rel=[1.0 if t in gt else 0.0 for t in recs[:k]]
    idcg=_dcg([1.0]*min(len(gt),k)); return _dcg(rel)/idcg if idcg>0 else 0.0
def _recall(recs, gt, k): return len(set(recs[:k])&gt)/len(gt) if gt else 0.0
def _prec(recs, gt, k):   return len(set(recs[:k])&gt)/min(k,len(recs)) if recs else 0.0


# ── Load + Filter + Per-User Split ────────────────────────────────────────────
async def load_data(db):
    log.info("=" * 60)
    log.info("📦 Load interactions…")
    raw = defaultdict(list)
    async for doc in db.interactions.find(
        {}, {"user_id":1,"track_id":1,"play_count":1,"last_played":1}
    ):
        raw[str(doc["user_id"])].append((
            str(doc["track_id"]),
            float(doc.get("play_count",1)),
            doc.get("last_played", datetime.min),
        ))

    total = sum(len(v) for v in raw.values())
    log.info(f"   Raw: {total:,} rows | {len(raw):,} users")

    # Đếm unique tracks/item total plays
    user_unique = defaultdict(set)
    item_total  = defaultdict(float)
    for uid, entries in raw.items():
        for iid, cnt, _ in entries:
            user_unique[uid].add(iid)
            item_total[iid] += cnt

    active_users  = {u for u,s in user_unique.items() if len(s) >= MIN_USER_UNIQUE_TRACKS}
    popular_items = {i for i,c in item_total.items()  if c >= MIN_ITEM_PLAYS}
    log.info(f"   Users: {len(user_unique):,} → {len(active_users):,} (>={MIN_USER_UNIQUE_TRACKS} unique)")
    log.info(f"   Items: {len(item_total):,} → {len(popular_items):,} (>={MIN_ITEM_PLAYS} plays)")

    # Aggregate (uid, iid) → (total_cnt, latest_ts)  [chỉ với filtered data]
    user_agg = {}
    for uid, entries in raw.items():
        if uid not in active_users: continue
        m = {}
        for iid, cnt, ts in entries:
            if iid not in popular_items: continue
            if iid not in m: m[iid] = [0.0, datetime.min]
            m[iid][0] += cnt
            if ts > m[iid][1]: m[iid][1] = ts
        if m: user_agg[uid] = m

    # ── Per-User 80/20 split ──────────────────────────────────────────────────
    log.info("✂️  Per-User 80/20 split…")
    train_agg    = {}   # uid → {iid: count}
    ground_truth = {}   # uid → set of test iid

    n_with_test = 0
    for uid, iid_map in user_agg.items():
        sorted_items = sorted(iid_map.items(), key=lambda x: x[1][1])
        split = max(1, int(len(sorted_items)*0.8))
        train_part = sorted_items[:split]
        test_part  = sorted_items[split:]
        train_agg[uid] = {iid: v[0] for iid, v in train_part}
        if test_part:
            ground_truth[uid] = {iid for iid,_ in test_part}
            n_with_test += 1

    log.info(f"   Users có train+test: {n_with_test:,}")

    # ── Build index ───────────────────────────────────────────────────────────
    user_set, item_set = {}, {}
    uid_to_counts = {}

    for uid, iid_cnt in train_agg.items():
        if uid not in user_set: user_set[uid] = len(user_set)
        entry = {}
        for iid, cnt in iid_cnt.items():
            if iid not in item_set: item_set[iid] = len(item_set)
            entry[item_set[iid]] = cnt
        uid_to_counts[user_set[uid]] = entry

    n_users = len(user_set)
    n_items = len(item_set)

    # Ground truth → item indices
    gt_indexed = defaultdict(set)
    test_in_train = 0; test_not_in_train = 0
    for uid, iid_set in ground_truth.items():
        if uid not in user_set: continue
        u_idx = user_set[uid]
        for iid in iid_set:
            if iid in item_set:
                gt_indexed[u_idx].add(item_set[iid])
                test_in_train += 1
            else:
                test_not_in_train += 1

    train_map = {u: set(im.keys()) for u,im in uid_to_counts.items()}
    eval_users = [
        u for u in gt_indexed
        if u in train_map and len(gt_indexed[u]) >= MIN_EVAL_TEST_ITEMS
    ][:MAX_EVAL_USERS]

    nnz = sum(len(v) for v in uid_to_counts.values())
    log.info(f"   Matrix: {n_users:,} × {n_items:,} | nnz={nnz:,} | density={nnz/(n_users*n_items)*100:.4f}%")
    log.info(f"   Test items IN item_set : {test_in_train:,}")
    log.info(f"   Test items NOT in set  : {test_not_in_train:,}  ← phải = 0 nếu data đúng")
    log.info(f"   gt_indexed users       : {len(gt_indexed):,}")
    log.info(f"   Eval users (>={MIN_EVAL_TEST_ITEMS} test items): {len(eval_users):,}")

    if not eval_users:
        log.error("❌ Không có eval users!")
        log.error(f"   Thử giảm MIN_EVAL_TEST_ITEMS (hiện = {MIN_EVAL_TEST_ITEMS})")
        log.error(f"   hoặc giảm MIN_ITEM_PLAYS (hiện = {MIN_ITEM_PLAYS})")
        raise RuntimeError("Không có eval users!")

    return {
        "uid_to_counts": uid_to_counts,
        "n_users": n_users, "n_items": n_items,
        "train_map": train_map,
        "ground_truth": gt_indexed,
        "eval_users": eval_users,
        # BM25 cần avg user length
        "avg_user_len": nnz / n_users if n_users else 1.0,
        "user_lengths": {u: sum(im.values()) for u,im in uid_to_counts.items()},
    }


# ── BM25 Confidence Matrix ─────────────────────────────────────────────────────
def build_bm25_matrix(uid_to_counts, n_users, n_items, alpha,
                      avg_user_len, user_lengths):
    """
    BM25 weighting: c_ui = 1 + alpha * bm25(tf, dl, avgdl)
      bm25 = tf*(K1+1) / (tf + K1*(1 - B + B*dl/avgdl))
    Normalize theo độ dài lịch sử user → tránh heavy listener dominate.
    """
    rows_u, rows_i, vals = [], [], []
    for u_idx, i_map in uid_to_counts.items():
        dl = user_lengths.get(u_idx, avg_user_len)
        for i_idx, tf in i_map.items():
            bm25 = tf * (BM25_K1 + 1) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * dl / avg_user_len))
            rows_u.append(u_idx)
            rows_i.append(i_idx)
            vals.append(1.0 + alpha * bm25)
    return sp.csr_matrix((vals,(rows_u,rows_i)), shape=(n_users,n_items), dtype=np.float32)


# ── Evaluate ───────────────────────────────────────────────────────────────────
def evaluate(model, user_items, train_map, gt, eval_users, n_items):
    ndcg_s=[]; rec_s={k:[] for k in K_VALUES}; pre_s={k:[] for k in K_VALUES}
    n_exc=0; n_no_gt=0; n_no_recs=0

    for u_idx in eval_users:
        row  = user_items[u_idx]
        gtu  = gt[u_idx]
        if not gtu: n_no_gt+=1; continue
        liked = train_map.get(u_idx, set())
        try:
            req_n = min(max(K_VALUES)*3+len(liked), n_items-1)
            ids,_ = model.recommend(u_idx, row, N=req_n, filter_already_liked_items=False)
            recs  = [int(i) for i in ids if int(i) not in liked][:max(K_VALUES)]
        except Exception as e:
            n_exc+=1; continue
        if not recs: n_no_recs+=1; continue
        ndcg_s.append(_ndcg(recs, gtu, 10))
        for k in K_VALUES:
            rec_s[k].append(_recall(recs,gtu,k))
            pre_s[k].append(_prec(recs,gtu,k))

    if not ndcg_s:
        log.warning(f"   Eval failed: no_gt={n_no_gt} exc={n_exc} no_recs={n_no_recs}")
        return None
    return {
        "users":          len(ndcg_s),
        "ndcg_at_10":     round(float(np.mean(ndcg_s)),5),
        "recall_at_10":   round(float(np.mean(rec_s[10])),5),
        "recall_at_20":   round(float(np.mean(rec_s[20])),5),
        "precision_at_10":round(float(np.mean(pre_s[10])),5),
        "precision_at_20":round(float(np.mean(pre_s[20])),5),
    }


# ── Main ───────────────────────────────────────────────────────────────────────
async def main():
    log.info("=" * 60)
    log.info("   ALS GRID SEARCH v4 — BM25 + Per-User Split + Diagnostics")
    log.info("=" * 60)

    client = AsyncIOMotorClient(MONGO_URI)
    data   = await load_data(client.get_default_database())
    client.close()

    combos = list(product(*PARAM_GRID.values()))
    keys   = list(PARAM_GRID.keys())
    total  = len(combos)
    log.info(f"\n🔍 Grid Search: {total} combinations\n")

    results=[]; best_score=-1; best_entry=None

    for i, combo in enumerate(combos, 1):
        p = dict(zip(keys, combo))
        log.info(f"[{i:3d}/{total}] f={p['factors']} it={p['iterations']} "
                 f"reg={p['regularization']} α={p['alpha']}")

        ui = build_bm25_matrix(
            data["uid_to_counts"], data["n_users"], data["n_items"],
            p["alpha"], data["avg_user_len"], data["user_lengths"]
        )
        t0 = time.time()
        try:
            model = AlternatingLeastSquares(
                factors=p["factors"], iterations=p["iterations"],
                regularization=p["regularization"], random_state=42, num_threads=1,
            )
            model.fit(ui.T.tocsr(), show_progress=False)
        except Exception as e:
            log.warning(f"   Training failed: {e}"); continue

        train_t = round(time.time()-t0, 2)
        m = evaluate(model, ui, data["train_map"], data["ground_truth"],
                     data["eval_users"], data["n_items"])
        if m is None: continue

        log.info(f"       NDCG@10={m['ndcg_at_10']:.4f} | R@10={m['recall_at_10']:.4f} | "
                 f"R@20={m['recall_at_20']:.4f} | P@10={m['precision_at_10']:.4f} | {train_t}s")

        entry = {"params": p, "metrics": m, "train_s": train_t}
        results.append(entry)
        if m["ndcg_at_10"] > best_score:
            best_score = m["ndcg_at_10"]; best_entry = entry
            log.info(f"       ⭐ New best = {best_score:.5f}")

    # ── Report ─────────────────────────────────────────────────────────────────
    results.sort(key=lambda r: r["metrics"]["ndcg_at_10"], reverse=True)
    log.info("\n" + "="*70)
    log.info("   TOP 10")
    log.info("="*70)
    log.info(f"{'#':<4}{'F':<6}{'I':<5}{'Reg':<7}{'α':<8}{'NDCG@10':<10}{'R@10':<9}{'P@10'}")
    for rank, r in enumerate(results[:10], 1):
        p,m = r["params"],r["metrics"]
        log.info(f"{rank:<4}{p['factors']:<6}{p['iterations']:<5}{p['regularization']:<7}"
                 f"{p['alpha']:<8}{m['ndcg_at_10']:<10.5f}{m['recall_at_10']:<9.5f}"
                 f"{m['precision_at_10']:.5f}")

    if best_entry:
        bp,bm = best_entry["params"],best_entry["metrics"]
        log.info("\n"+"="*60)
        log.info("   🏆 BEST CONFIGURATION")
        log.info("="*60)
        for k,v in bp.items(): log.info(f"   {k:<22} = {v}")
        log.info("")
        log.info(f"   NDCG@10       = {bm['ndcg_at_10']:.5f}")
        log.info(f"   Recall@10     = {bm['recall_at_10']:.5f}")
        log.info(f"   Recall@20     = {bm['recall_at_20']:.5f}")
        log.info(f"   Precision@10  = {bm['precision_at_10']:.5f}")
        log.info(f"   Users eval    = {bm['users']}")
        log.info("="*60)
        log.info(f"""
✅ Cập nhật vào als_service.py:
    ALPHA         = {bp['alpha']}
    BM25_K1       = {BM25_K1}
    BM25_B        = {BM25_B}
    factors       = {bp['factors']}
    iterations    = {bp['iterations']}
    regularization= {bp['regularization']}
""")

    out = {
        "timestamp":   datetime.now(timezone.utc).isoformat(),
        "config": {"MIN_USER_UNIQUE_TRACKS":MIN_USER_UNIQUE_TRACKS,
                   "MIN_ITEM_PLAYS":MIN_ITEM_PLAYS,
                   "MIN_EVAL_TEST_ITEMS":MIN_EVAL_TEST_ITEMS,
                   "BM25_K1":BM25_K1, "BM25_B":BM25_B,
                   "param_grid":PARAM_GRID},
        "best_params":  best_entry["params"]  if best_entry else None,
        "best_metrics": best_entry["metrics"] if best_entry else None,
        "all_results":  results,
    }
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "grid_search_results.json")
    with open(path,"w",encoding="utf-8") as f: json.dump(out,f,indent=2,ensure_ascii=False)
    log.info(f"💾 Saved → {path}")


if __name__ == "__main__":
    asyncio.run(main())
