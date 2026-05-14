import implicit
import implicit.evaluation
from implicit.nearest_neighbours import bm25_weight

# 1. Tạo MỘT ma trận duy nhất từ toàn bộ data (đã lọc user >= 15 bài)
# Ma trận user_items có dạng: Hàng là User, Cột là Item
user_items = sp.csr_matrix((data, (rows_u, rows_i)), shape=(n_users, n_items))

# 2. Để thư viện TỰ ĐỘNG chia Train/Test (Chia cực kỳ chuẩn xác)
# Nó sẽ tự động lấy 20% bài hát CỦA TỪNG USER đưa vào test
train_user_items, test_user_items = implicit.evaluation.train_test_split(
    user_items, 
    train_percentage=0.8, 
    random_state=42
)

# 3. Trọng số hóa bằng BM25 (Phải lật ma trận thành Item-User trước khi fit)
# train_user_items.T lật ma trận lại thành (Items x Users)
item_users_train = bm25_weight(train_user_items.T, K1=100, B=0.8)

# 4. Train mô hình
model = implicit.als.AlternatingLeastSquares(factors=64, iterations=30, regularization=0.1, random_state=42)
model.fit(item_users_train)

# 5. Đánh giá (Thư viện tự lo việc map ID, né bài cũ, tính NDCG chính xác)
metrics = implicit.evaluation.ranking_metrics_at_k(
    model, 
    train_user_items, # Đưa train vào để nó biết đường né bài cũ
    test_user_items,  # Đáp án
    K=10, 
    show_progress=True, 
    num_threads=1
)

print(f"BM25 + ALS -> NDCG@10: {metrics['ndcg']} | Precision@10: {metrics['precision']}")