# Hướng Dẫn Tải Dataset

## Bước 1: Tải 2 Dataset từ Kaggle

### Dataset 1: Spotify Audio Features (160K Tracks)
- **URL:** https://www.kaggle.com/datasets/yamaerenay/spotify-dataset-19212020-600k-tracks
- **File cần thiết:** `tracks.csv` hoặc `tracks_features.csv`
- **Đặt vào:** `data/raw/spotify_tracks.csv`

### Dataset 2: Last.fm User Listening History
- **URL:** https://www.kaggle.com/datasets/neferfufi/lastfm
  - Hoặc: https://www.kaggle.com/datasets/pcbreviglieri/lastfm-music-artist-scrobbles
- **File cần thiết:** File TSV/CSV chứa các cột: user_id, artist_name, track_name, play_count
- **Đặt vào:** `data/raw/lastfm_interactions.tsv`

## Bước 2: Cấu Trúc Thư Mục raw/
```
data/
└── raw/
    ├── spotify_tracks.csv      ← Spotify audio features
    └── lastfm_interactions.tsv ← Last.fm user interactions
```

## Bước 3: Cài Dependencies và Chạy Scripts
```bash
cd data/
pip install -r requirements.txt
python 01_preprocess.py
python 02_seed_mongodb.py
```

## Định Dạng Expected

### spotify_tracks.csv (cần có các cột):
- `id` hoặc `track_id`: ID bài hát
- `name` hoặc `title`: Tên bài hát
- `artists`: Tên nghệ sĩ
- `danceability`, `energy`, `valence`, `tempo`
- `acousticness`, `liveness`, `speechiness`
- `popularity`: Độ nổi tiếng (0-100)
- `explicit`: Boolean

### lastfm_interactions.tsv (cần có các cột):
- `user_id` hoặc `user`: ID người dùng
- `artist_name` hoặc `artist`: Tên nghệ sĩ
- `track_name` hoặc `track`: Tên bài hát
- `play_count` hoặc `count` hoặc `plays`: Số lần nghe

> **Lưu ý:** Script `01_preprocess.py` tự động detect format của file và xử lý linh hoạt.
