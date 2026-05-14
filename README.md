# 🎵 MusicRec — Hệ Thống Gợi Ý Âm Nhạc Cá Nhân Hóa (Hybrid Model)

Hệ thống gợi ý âm nhạc full-stack kết hợp **Collaborative Filtering (ALS)** và **Content-Based Filtering (Cosine Similarity)** để cung cấp trải nghiệm nghe nhạc cá nhân hóa real-time.

---

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React (Vite) + CSS |
| Backend | NestJS (TypeScript 5) |
| AI Service | FastAPI (Python 3.10+) |
| Database | MongoDB |
| Cache | Redis |
| Audio Preview | iTunes Search API |

---

## 📂 Cấu Trúc Dự Án

```
Final/
├── docker-compose.yml     # MongoDB + Redis
├── data/                  # Dataset preprocessing
│   ├── 01_preprocess.py   # Fuzzy join Spotify + Last.fm
│   ├── 02_seed_mongodb.py # Seed vào MongoDB
│   └── raw/               # ← đặt dataset tải về ở đây
├── ai-service/            # FastAPI AI service (port 8000)
├── backend/               # NestJS API (port 3001)
└── frontend/              # React app (port 5173)
```

---

## 🚀 Hướng Dẫn Chạy Dự Án

### Yêu Cầu
- **Docker Desktop** (để chạy MongoDB + Redis)
- **Node.js** v20+
- **Python** 3.10+

---

### Bước 1: Khởi Động MongoDB + Redis

```bash
docker-compose up -d
```

Kiểm tra: MongoDB tại `localhost:27017`, Redis tại `localhost:6379`

---

### Bước 2: Chuẩn Bị Dataset và Seed MongoDB

#### 2a. Tải Dataset (xem `data/README_DATA.md` để biết URL)
- Đặt `spotify_tracks.csv` vào `data/raw/`
- Đặt `lastfm_interactions.tsv` vào `data/raw/`

#### 2b. Cài Python Dependencies và Chạy Pipeline

```bash
cd data
pip install -r requirements.txt
cp .env.example .env

# Bước 1: Preprocess + fuzzy join
python 01_preprocess.py

# Bước 2: Seed vào MongoDB
python 02_seed_mongodb.py
```

> **Lưu ý:** Nếu không có Last.fm dataset, script sẽ tự tạo synthetic interactions.

**Tài khoản admin mặc định sau seed:**
- Username: `admin`
- Password: `Admin@123`

---

### Bước 3: Khởi Động AI Service (FastAPI)

```bash
cd ai-service
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

---

### Bước 4: Khởi Động Backend (NestJS)

```bash
cd backend
cp .env.example .env
npm run start:dev
```

API base: http://localhost:3001/api

---

### Bước 5: Khởi Động Frontend (React)

```bash
cd frontend
cp .env.example .env
npm run dev
```

Mở trình duyệt: http://localhost:5173

---

## 👤 Tài Khoản Mặc Định

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `Admin@123` |
| User | *(tự đăng ký)* | *(tự chọn)* |

---

## 🤖 Luồng Hoạt Động Của Hệ Thống

### Luồng Gợi Ý Hybrid (Real-time)

```
User click nghe Track A
    ↓
POST /api/play/:trackId
    ├── Upsert interactions (MongoDB)
    └── pushRecentTrack (Redis, TTL 30 phút)

User vào Trang Chủ
    ↓
GET /api/recommendations
    ↓ (NestJS đọc Redis)
GET /ai/hybrid-recommend?user_id=X&recent_tracks=A
    ├── CF: daily_recommendations (pre-computed ALS)
    ├── CB: cosine similarity với Track A
    └── final_score = 0.6 * CB + 0.4 * CF
    ↓
NestJS query MongoDB → trả metadata đầy đủ về React
```

### Luồng Cold-Start (User Mới)

```
User mới đăng ký → Onboarding (chọn genres + mood)
    ↓
GET /ai/cold-start?genres=pop,rnb
    └── Filter tracks theo genre → sort by total_plays → Top 30
```

### Luồng Popup Real-time

```
User click nghe Track
    ↓
GET /api/recommendations/similar/:trackId
    ↓
GET /ai/content-similar?track_id=X&top_k=5
    └── Cosine Similarity → 5 bài gần nhất
    ↓
RecommendPopup hiển thị (floating window)
```

---

## 📊 Chạy ALS Training (Admin Only)

1. Đăng nhập bằng tài khoản `admin`
2. Vào trang **Admin Dashboard** (`/admin`)
3. Click **"Run ALS Training"**
4. Sau khi xong, click **"Run Evaluation"** để xem metrics

> Training có thể mất **2-10 phút** tuỳ kích thước dataset.

---

## 📈 Evaluation Metrics

| Metric | Mô tả |
|--------|-------|
| NDCG@10 | Đo chất lượng thứ tự xếp hạng top 10 |
| Recall@10 | Tỷ lệ bài thực sự nghe xuất hiện trong top 10 |
| Recall@20 | Tỷ lệ bài thực sự nghe xuất hiện trong top 20 |
| Coverage | % catalog bài hát từng được gợi ý |

Split: **80% train / 20% test** theo thời gian (`last_played`)

---

## 🌐 API Endpoints

### Auth
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/auth/register` | Đăng ký tài khoản |
| POST | `/api/auth/login` | Đăng nhập, trả JWT |

### Users (JWT required)
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/users/me` | Lấy profile |
| PUT | `/api/users/me/onboarding` | Lưu preferences |
| PUT | `/api/users/me/profile` | Cập nhật demographics |

### Tracks (JWT required)
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/tracks/search?q=` | Tìm kiếm full-text |
| GET | `/api/tracks/:id` | Chi tiết track |
| GET | `/api/tracks/:id/itunes-preview` | Lấy preview URL (iTunes) |

### Play & Recommendations (JWT required)
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/play/:trackId` | Ghi nhận lượt nghe |
| GET | `/api/recommendations` | Hybrid recommendations |
| GET | `/api/recommendations/similar/:id` | 5 bài similar (popup) |

### Admin (JWT + role=admin)
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/admin/stats` | Dashboard stats |
| POST | `/api/admin/trigger-training` | Trigger ALS |
| GET | `/api/admin/evaluate` | Chạy evaluation |
| GET | `/api/admin/users` | Danh sách users |
| DELETE | `/api/admin/users/:id` | Xóa user |

---

## 🔧 Troubleshooting

**MongoDB không kết nối được:**
```bash
docker-compose ps   # Kiểm tra status
docker-compose restart mongodb
```

**NestJS lỗi EBADENGINE (Node version):**
> Chỉ là warning, không ảnh hưởng chức năng. Bỏ qua.

**FastAPI không tìm thấy model:**
> Cần chạy Training ít nhất 1 lần qua Admin Dashboard trước khi dùng hybrid recommendations.

**iTunes preview trả về null:**
> Một số bài hát không có preview 30s trên iTunes. Hệ thống vẫn ghi nhận play_count bình thường.

---

## 📝 Dataset Sources

- **Spotify Audio Features**: [Kaggle - Spotify Dataset 1921-2020](https://www.kaggle.com/datasets/yamaerenay/spotify-dataset-19212020-600k-tracks)
- **Last.fm Interactions**: [Kaggle - Last.fm Dataset](https://www.kaggle.com/datasets/neferfufi/lastfm)
