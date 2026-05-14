# Kế Hoạch Triển Khai: Hệ Thống Gợi Ý Âm Nhạc Cá Nhân Hóa (Hybrid Model)

## Các Quyết Định Kỹ Thuật Quan Trọng

- **Matching Strategy:** Fuzzy Matching với `rapidfuzz`, ngưỡng ≥ 90%
- **Quy mô seed:** 50K tracks, 5K users, ~300K interactions
- **Content Vector (7 features):** danceability, energy, valence, tempo/250, acousticness, liveness, speechiness
- **Cold-start:** Filter theo genre preferences → sort by total_plays → Top 30
- **Batch Job:** Admin trigger thủ công qua Dashboard
- **Redis:** List, sliding window TTL 30 phút, giữ 10 bài gần nhất
- **Preview audio:** iTunes Search API (free, no API key)
- **Admin mặc định:** username: admin / password: Admin@123
- **Hybrid formula:** 0.6 × score_CB + 0.4 × score_CF

## Tech Stack
- **Frontend:** React (Vite) + CSS
- **Backend:** NestJS (TypeScript 5)
- **AI Service:** FastAPI (Python 3.10+)
- **Database:** MongoDB
- **Cache:** Redis

## Cấu Trúc Thư Mục
```
Final/
├── data/                  # Data pipeline
├── ai-service/            # FastAPI
├── backend/               # NestJS
├── frontend/              # React
└── docker-compose.yml
```

## API Map
| Method | Endpoint | Service |
|--------|----------|---------|
| POST | /api/auth/register | NestJS |
| POST | /api/auth/login | NestJS |
| GET | /api/users/me | NestJS |
| PUT | /api/users/me/onboarding | NestJS |
| GET | /api/tracks/search?q= | NestJS |
| GET | /api/tracks/:id/itunes-preview | NestJS |
| POST | /api/play/:trackId | NestJS |
| GET | /api/recommendations | NestJS |
| GET | /api/recommendations/similar/:trackId | NestJS |
| POST | /api/admin/trigger-training | NestJS |
| GET | /api/admin/stats | NestJS |
| GET | /api/admin/evaluate | NestJS |
| POST | /ai/train | FastAPI |
| GET | /ai/hybrid-recommend | FastAPI |
| GET | /ai/cold-start | FastAPI |
| GET | /ai/content-similar | FastAPI |
| GET | /ai/evaluate | FastAPI |
