import json
import os
import numpy as np
import scipy.sparse as sp
import implicit
import implicit.evaluation
from implicit.nearest_neighbours import bm25_weight
from collections import defaultdict

def main():
    # Cập nhật đường dẫn: Nhảy ra ngoài 1 cấp (..), vào thư mục data/processed/
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH = os.path.join(BASE_DIR, "..", "data", "processed", "interactions.json")

    print(f"1. Đang đọc dữ liệu từ: {DATA_PATH}")
    
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            interactions = json.load(f)
    except FileNotFoundError:
        print(f"❌ LỖI: Không tìm thấy file tại đường dẫn: {os.path.abspath(DATA_PATH)}")
        return

    # 2. Lọc User có >= 15 bài độc nhất và Item có >= 10 lượt nghe
    user_unique_items = defaultdict(set)
    item_total_plays = defaultdict(float)
    
    for doc in interactions:
        uid = str(doc["_user_idx"])   # ĐÃ SỬA
        iid = str(doc["_track_idx"])  # ĐÃ SỬA
        cnt = float(doc.get("play_count", 1))
        
        user_unique_items[uid].add(iid)
        item_total_plays[iid] += cnt

    active_users = {u for u, items in user_unique_items.items() if len(items) >= 0}
    popular_items = {i for i, c in item_total_plays.items() if c >= 0}

    print(f"   -> Giữ lại {len(active_users)} Users và {len(popular_items)} Items")

    # 3. Tạo từ điển Mapping và xây dựng Ma trận
    user_map, item_map = {}, {}
    rows_u, rows_i, data = [], [], []

    for doc in interactions:
        uid = str(doc["_user_idx"])   # ĐÃ SỬA
        iid = str(doc["_track_idx"])  # ĐÃ SỬA
        if uid in active_users and iid in popular_items:
            if uid not in user_map: user_map[uid] = len(user_map)
            if iid not in item_map: item_map[iid] = len(item_map)
            
            rows_u.append(user_map[uid])
            rows_i.append(item_map[iid])
            data.append(float(doc.get("play_count", 1)))

    n_users, n_items = len(user_map), len(item_map)
    user_items = sp.csr_matrix((data, (rows_u, rows_i)), shape=(n_users, n_items))
    print(f"2. Ma trận đã tạo: {n_users} x {n_items}")

    # 4. Chia Train/Test TỰ ĐỘNG bằng thư viện Implicit
    print("3. Đang chia Train/Test...")
    train_user_items, test_user_items = implicit.evaluation.train_test_split(
        user_items, train_percentage=0.8, random_state=42
    )

    # 5. Áp dụng BM25 (BỎ .T ĐI VÀ THÊM .tocsr())
    print("4. Áp dụng trọng số BM25 và Huấn luyện ALS...")
    # Sửa dòng này:
    train_user_items_bm25 = bm25_weight(train_user_items, K1=100, B=0.8).tocsr()
    
    model = implicit.als.AlternatingLeastSquares(factors=32, iterations=30, regularization=0.1, random_state=42)
    # Sửa dòng này:
    model.fit(train_user_items_bm25)

    # 6. Đánh giá tự động
    print("5. Đang chấm điểm NDCG...")
    metrics = implicit.evaluation.ranking_metrics_at_k(
        model, train_user_items, test_user_items, K=10, show_progress=False, num_threads=1
    )

    print("\n" + "="*40)
    print("🎯 KẾT QUẢ CUỐI CÙNG:")
    print(f"NDCG@10      : {metrics['ndcg']:.5f}")
    print(f"Precision@10 : {metrics['precision']:.5f}")
    print("="*40)

if __name__ == "__main__":
    main()