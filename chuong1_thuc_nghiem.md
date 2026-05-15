# CHƯƠNG 1: THỰC NGHIỆM VÀ ĐÁNH GIÁ

---

## 1.1 Bộ Dữ Liệu (Dataset)

### 1.1.1 Nguồn dữ liệu

Hệ thống sử dụng hai bộ dữ liệu nguồn gốc từ nền tảng Last.fm:

| Tệp | Mô tả | Kích thước gốc |
|-----|--------|---------------|
| `Music Info.csv` | Thông tin bài hát: tiêu đề, nghệ sĩ, audio features (danceability, energy, valence, tempo, acousticness, liveness, speechiness) | ~13,000+ bài |
| `User Listening History.csv` | Lịch sử nghe nhạc: cặp (user_id, track_id, play_count) | ~600 MB, >10 triệu dòng |

### 1.1.2 Đặc trưng bộ dữ liệu sau tiền xử lý

| Thuộc tính | Giá trị |
|-----------|---------|
| Số người dùng | **46,459** |
| Số bài hát | **13,646** |
| Số cặp tương tác | **2,586,949** |
| Mật độ ma trận | ~0.41% (sparse) |
| Tổng lượt nghe | > 15 triệu |

---

## 1.2 Tiền Xử Lý Dữ Liệu

### 1.2.1 Quy trình tổng thể

Script: `data/01_preprocess.py`

```
Music Info.csv ──┐
                 ├── Join (track_id) ── Lọc iterative ── Output JSON
User History.csv ┘
```

### 1.2.2 Các bước tiền xử lý

**Bước 1 — Tải và làm sạch dữ liệu gốc**
- Đọc `Music Info.csv` theo từng chunk 500,000 dòng để tránh tràn bộ nhớ
- Loại bỏ các dòng thiếu `track_id`, `title`, `artist`; loại trùng lặp theo `track_id`
- Aggregate (tổng hợp) play_count cho mỗi cặp (user, track) nếu có nhiều dòng

**Bước 2 — Lấy Top N người dùng tích cực nhất**
- Chỉ giữ lại tối đa `MAX_USERS = 100,000` người dùng có tổng lượt nghe nhiều nhất
- Loại các cặp (user, track) có play_count < 1

**Bước 3 — Lọc iterative (người dùng ↔ bài hát)**

Áp dụng bộ lọc lặp cho đến khi tập dữ liệu ổn định:

| Ngưỡng | Điều kiện |
|--------|-----------|
| `MIN_USER_UNIQUE_TRACKS = 30` | Người dùng phải nghe **≥ 30 bài khác nhau** |
| `MIN_TRACK_TOTAL_PLAYS = 50` | Bài hát phải có tổng lượt nghe **> 50** (tính từ user hợp lệ) |

> **Lý do dùng lọc iterative:** Khi loại một bài hát (thiếu plays), người dùng có thể mất đủ số bài → bị loại → bài khác mất plays → lại bị loại. Vòng lặp đảm bảo hội tụ ổn định.

**Bước 4 — Tạo content_vector**

Mỗi bài hát được ánh xạ thành vector 7 chiều từ audio features:

```python
content_vector = [danceability, energy, valence,
                  tempo/250.0, acousticness, liveness, speechiness]
```

Vector này được dùng cho mô hình Content-Based Filtering.

**Bước 5 — Xuất file**

Ba file JSON được tạo ra trong thư mục `data/processed/`:
- `tracks.json` — 13,646 bài hát kèm content_vector
- `users.json` — 46,459 người dùng
- `interactions.json` — 2,586,949 cặp (user_idx, track_idx, play_count)

---

## 1.3 Xây Dựng Mô Hình ALS (Collaborative Filtering)

### 1.3.1 Tổng quan

**Alternating Least Squares (ALS)** là thuật toán Matrix Factorization cho bài toán implicit feedback. Thay vì dùng rating trực tiếp, ALS phân tích ma trận tương tác người dùng–bài hát thành hai ma trận thấp chiều:

$$\mathbf{R} \approx \mathbf{U} \cdot \mathbf{I}^T$$

Trong đó:
- **R** ∈ ℝ^{n_users × n_items}: ma trận tương tác (play_count)
- **U** ∈ ℝ^{n_users × f}: ma trận embedding người dùng
- **I** ∈ ℝ^{n_items × f}: ma trận embedding bài hát
- **f = 64**: số chiều latent factor

### 1.3.2 BM25 Confidence Weighting

Thay vì dùng play_count thô, hệ thống áp dụng **BM25 weighting** để chuẩn hóa tần suất nghe:

$$c_{ui} = \frac{r_{ui} \cdot (K_1 + 1)}{K_1 \cdot \left(1 - B + B \cdot \frac{dl_u}{avgdl}\right) + r_{ui}}$$

| Tham số | Giá trị | Ý nghĩa |
|---------|---------|---------|
| K₁ | 1.0 | Độ bão hòa tần suất |
| B | 0.8 | Mức độ chuẩn hóa theo độ dài |
| dl_u | Tổng plays của user u | Document length |
| avgdl | Trung bình plays của tất cả users | Average document length |

> **Lý do chọn BM25:** Người dùng nghe một bài 100 lần không nên có ảnh hưởng gấp 100 lần so với nghe 1 lần. BM25 tạo ra hàm saturation phi tuyến, giúp mô hình ổn định hơn.

### 1.3.3 Grid Search tìm siêu tham số

Thực hiện Grid Search trên 5 giá trị mỗi tham số, tổng cộng nhiều tổ hợp. Chia dữ liệu 80/20 bằng `implicit.evaluation.train_test_split`. Đánh giá theo NDCG@10.

**Tham số tốt nhất (best configuration):**

| Siêu tham số | Giá trị | Mô tả |
|-------------|---------|-------|
| factors (f) | **64** | Số chiều latent factor |
| iterations | **20** | Số vòng lặp ALS |
| regularization (λ) | **0.1** | Hệ số điều chuẩn L2 |
| BM25 K₁ | **1.0** | Tham số BM25 |
| BM25 B | **0.8** | Tham số BM25 (cố định) |

### 1.3.4 Quy trình huấn luyện (Production)

```
interactions (MongoDB)
       ↓
Lọc: MIN_USER_UNIQUE_TRACKS=30 (seed) / 5 (real users)
      MIN_ITEM_PLAYS=50
       ↓
Build sparse matrix (users × items)
       ↓
BM25 weighting (K1=1.0, B=0.8)
       ↓  [Phase 1 - Evaluation]
Train/Test split 80/20 → ALS eval model → Log NDCG/Recall/Precision
       ↓  [Phase 2 - Production]
Train ALS trên 100% data → lưu model.pkl
       ↓
Real-time inference: Folding-in (recalculate_user=True)
```

### 1.3.5 Folding-in cho Real-time Recommendation

Khi người dùng nghe thêm bài mới, hệ thống không retrain toàn bộ mô hình. Thay vào đó, áp dụng **Folding-in**:

1. Fetch tương tác hiện tại từ MongoDB
2. Build sparse row mới (1 × n_items)
3. Áp BM25 weighting
4. Giải ALS theo dạng closed-form: $\mathbf{u} = (\mathbf{I}^T \mathbf{C}^u \mathbf{I} + \lambda \mathbf{I}_f)^{-1} \mathbf{I}^T \mathbf{C}^u \mathbf{p}^u$
5. Item factors **không thay đổi**

---

## 1.4 Xây Dựng Mô Hình Content-Based Filtering

### 1.4.1 Tổng quan

Mô hình Content-Based Filtering sử dụng **Cosine Similarity** giữa các vector đặc trưng âm thanh (audio features) để tìm bài hát tương tự.

### 1.4.2 Content Vector

Mỗi bài hát được biểu diễn bằng vector 7 chiều:

| Chiều | Feature | Mô tả |
|-------|---------|-------|
| 1 | danceability | Mức độ thích hợp để nhảy (0–1) |
| 2 | energy | Cường độ và hoạt động âm thanh (0–1) |
| 3 | valence | Tích cực về mặt âm nhạc (0–1) |
| 4 | tempo/250 | Nhịp độ được chuẩn hóa |
| 5 | acousticness | Mức độ acoustic (0–1) |
| 6 | liveness | Phát hiện âm thanh live (0–1) |
| 7 | speechiness | Mức độ có lời nói (0–1) |

Các vector được **L2-normalize** để tính cosine similarity qua dot product:

$$\text{sim}(a, b) = \frac{\mathbf{a} \cdot \mathbf{b}}{|\mathbf{a}||\mathbf{b}|} = \hat{\mathbf{a}} \cdot \hat{\mathbf{b}}$$

### 1.4.3 Quy trình gợi ý

1. Lấy top-5 bài nghe nhiều nhất trong lịch sử của user
2. Aggregate cosine similarity score với toàn bộ catalog
3. Loại bỏ bài đã nghe
4. Trả về top-N bài có score cao nhất

### 1.4.4 Ưu điểm và hạn chế

| Ưu điểm | Hạn chế |
|---------|---------|
| Không cần dữ liệu từ user khác | Feature vector chỉ có 7 chiều, hạn chế sắc thái |
| Hoạt động ngay cả với new item | Không thể nắm bắt sở thích tinh tế như CF |
| Không cần retrain khi dataset thay đổi | CB đơn thuần cho kết quả thấp hơn ALS |
| Lý giải được (feature-based) | Dễ bị "filter bubble" |

---

## 1.5 Đánh Giá Mô Hình

### 1.5.1 Phương pháp đánh giá

**Phương pháp tách tập:**
- Dùng `sklearn.model_selection.train_test_split` với `test_size=0.2`, `random_state=42`
- Tập train: 2,069,559 interactions (80%)
- Tập test: 517,390 interactions (20%)
- Số user đánh giá: 500 users (ngẫu nhiên từ tập overlap train–test)

**Thư viện tính chỉ số:**
- `sklearn.metrics.ndcg_score` → NDCG@10
- `sklearn.metrics.precision_score` → Precision@10
- `sklearn.metrics.recall_score` → Recall@10
- `implicit.evaluation.ranking_metrics_at_k` → NDCG@10, Precision@10 (cho ALS)

> **Ghi chú về ALS:** Kết quả ALS được lấy từ Grid Search dùng `implicit.evaluation.train_test_split` (80/20) và `implicit.evaluation.ranking_metrics_at_k`.

### 1.5.2 Kết quả đánh giá

| Mô hình | NDCG@10 | Precision@10 | Recall@10 |
|---------|--------:|-------------:|----------:|
| **ALS – Collaborative Filtering** (best config: f=64, iter=20, reg=0.1, K₁=1.0) | **0.22664** | **0.21048** | **0.20000** |
| **Hybrid** (0.6·CF + 0.4·CB) | 0.22607 | 0.17400 | 0.16920 |
| **Content-Based** (Cosine Similarity) | 0.00172 | 0.00140 | 0.00179 |

> Kết quả ALS lấy từ Grid Search (implicit.evaluation, train split 80%). Kết quả CB và Hybrid từ eval_cb_hybrid.py (sklearn, 500 users).

### 1.5.3 Phân tích kết quả

**Collaborative Filtering (ALS):**
- Đạt NDCG@10 = **0.22664** — kết quả tốt nhất trong ba mô hình
- Nhờ khai thác hiệu quả lịch sử hành vi cộng đồng (46,459 users)
- BM25 weighting giúp mô hình ổn định hơn log1p truyền thống

**Hybrid (0.6·CF + 0.4·CB):**
- NDCG@10 = **0.22607** — gần tương đương ALS (chênh 0.00057)
- Kết hợp giúp đa dạng gợi ý và hoạt động tốt với new user (có CB làm fallback)
- Trong môi trường production, Hybrid được dùng ở trang chủ và popup gợi ý

**Content-Based (Cosine Similarity):**
- NDCG@10 = **0.00172** — thấp đáng kể
- **Nguyên nhân:** Vector 7 chiều quá thô để phân biệt sở thích cá nhân; người dùng có lịch sử nghe đa dạng nên "trung bình" vector gần bằng nhau
- Vai trò thực tế: tìm bài tương tự theo âm thanh (tab Taste Match, popup), không dùng độc lập để gợi ý cá nhân hóa

### 1.5.4 Nhận xét tổng quan

```
ALS (Collab)  ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  0.22664
Hybrid        ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  0.22607
CB            ▏                          0.00172
              0        0.1       0.2   NDCG@10
```

Kết quả cho thấy:
1. **ALS chiếm ưu thế** trong bài toán gợi ý cá nhân hóa nhờ học được pattern hành vi từ cộng đồng lớn
2. **Hybrid gần như tương đương ALS** với lợi thế thêm: đa dạng danh sách gợi ý và xử lý cold-start
3. **CB phù hợp cho use case khác**: tìm bài tương tự (similarity search), không phải personalized recommendation
4. Trong hệ thống production, ba mô hình được phân vai rõ ràng:
   - Trang chủ & Popup → **Hybrid**
   - Tab Collab Picks → **ALS**
   - Tab Taste Match → **CB**

---

*Script đánh giá: `ai-service/eval_cb_hybrid.py` (CB + Hybrid) và `ai-service/als_grid_search.py` (ALS)*
