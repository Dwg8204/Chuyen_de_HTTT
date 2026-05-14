#!/usr/bin/env python3
"""
01_preprocess.py - Tiền xử lý dữ liệu từ Music Info.csv + User Listening History.csv
Join trực tiếp qua track_id (không cần fuzzy matching).
Output: processed/tracks.json, processed/users.json, processed/interactions.json
"""
import os, json, random, logging
import pandas as pd
import numpy as np
from tqdm import tqdm

# ── Config ────────────────────────────────────────────────────────────────────
MUSIC_INFO_FILE    = "raw/Music Info.csv"
HISTORY_FILE       = "raw/User Listening History.csv"
OUTPUT_DIR         = "processed"
MAX_USERS          = 5_000     # Lấy top N user có nhiều lượt nghe nhất
MIN_PLAYS          = 1         # Loại bỏ cặp (user, track) có play_count < N
RANDOM_SEED        = 42

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────
GENRES_ALL = ['pop','rock','rnb','indie','acoustic','hiphop','jazz','electronic']
MOODS      = ['energetic','chill','happy','melancholic','focused']

def safe_float(val, default=0.5):
    try: return float(val)
    except: return default

def genre_heuristic(row) -> list:
    d  = safe_float(row.get('danceability',  .5))
    e  = safe_float(row.get('energy',        .5))
    v  = safe_float(row.get('valence',       .5))
    a  = safe_float(row.get('acousticness',  .5))
    sp = safe_float(row.get('speechiness',   .5))
    tags = []
    if d > .7  and e > .6:   tags.append('pop')
    if e > .8  and v < .4:   tags.append('rock')
    if d > .75 and sp > .1:  tags.append('rnb')
    if a > .6  and e < .5:   tags.append('indie')
    if a > .7:                tags.append('acoustic')
    if sp > .3:               tags.append('hiphop')
    if e < .4  and v > .5:   tags.append('jazz')
    if e > .85:               tags.append('electronic')
    # Fallback: dùng cột genre từ CSV nếu có
    if not tags and pd.notna(row.get('genre','')):
        raw_genre = str(row.get('genre','')).strip().lower()
        for g in GENRES_ALL:
            if g in raw_genre:
                tags.append(g)
    return tags or ['pop']

def content_vector(row) -> list:
    return [
        safe_float(row.get('danceability',  .5)),
        safe_float(row.get('energy',        .5)),
        safe_float(row.get('valence',       .5)),
        safe_float(row.get('tempo',       120)) / 250.0,
        safe_float(row.get('acousticness',  .5)),
        safe_float(row.get('liveness',      .5)),
        safe_float(row.get('speechiness',   .5)),
    ]


# ── Load Music Info ───────────────────────────────────────────────────────────
def load_music_info() -> pd.DataFrame:
    log.info(f"Loading Music Info: {MUSIC_INFO_FILE}")
    df = pd.read_csv(MUSIC_INFO_FILE, dtype=str)
    log.info(f"  Raw rows: {len(df):,} | cols: {list(df.columns)}")

    # Đổi tên cột để khớp schema cũ
    rename = {}
    if 'name'   in df.columns: rename['name']   = 'title'
    if 'artist' in df.columns: rename['artist']  = 'artist'   # giữ nguyên
    df = df.rename(columns=rename)

    required = ['track_id', 'title', 'artist']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Thiếu cột '{col}' trong Music Info.csv. Cột hiện có: {list(df.columns)}")

    df = df.dropna(subset=['track_id', 'title', 'artist'])
    df = df[df['track_id'].str.strip() != '']
    df = df.drop_duplicates(subset=['track_id'])
    log.info(f"  Sau khi làm sạch: {len(df):,} tracks unique")
    return df


# ── Load User Listening History ───────────────────────────────────────────────
def load_history() -> pd.DataFrame:
    log.info(f"Loading User Listening History: {HISTORY_FILE}")
    # File lớn (~600MB) → đọc theo chunks để tránh OOM
    chunks = []
    chunk_size = 500_000
    for chunk in tqdm(pd.read_csv(HISTORY_FILE, dtype={'track_id': str, 'user_id': str, 'playcount': str},
                                  chunksize=chunk_size), desc="Reading history"):
        chunk = chunk.rename(columns={'playcount': 'play_count'})
        chunk['play_count'] = pd.to_numeric(chunk['play_count'], errors='coerce').fillna(0).astype(int)
        chunk = chunk[chunk['play_count'] >= MIN_PLAYS]
        chunks.append(chunk)

    df = pd.concat(chunks, ignore_index=True)
    log.info(f"  Raw rows sau lọc MIN_PLAYS={MIN_PLAYS}: {len(df):,}")

    # Aggregate: tổng play_count nếu 1 user có nhiều dòng cho 1 track
    df = df.groupby(['user_id', 'track_id'], as_index=False)['play_count'].sum()
    log.info(f"  Sau aggregate: {len(df):,} cặp (user, track)")
    log.info(f"  Users: {df['user_id'].nunique():,} | Tracks: {df['track_id'].nunique():,}")
    return df


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    # 1. Load dữ liệu
    music_df   = load_music_info()
    history_df = load_history()

    # 2. Chỉ giữ interactions có track_id tồn tại trong Music Info
    valid_track_ids = set(music_df['track_id'])
    history_df = history_df[history_df['track_id'].isin(valid_track_ids)]
    log.info(f"  Sau join với Music Info: {len(history_df):,} interactions | "
             f"{history_df['user_id'].nunique():,} users | "
             f"{history_df['track_id'].nunique():,} tracks")

    # 3. Lấy top MAX_USERS user có tổng lượt nghe nhiều nhất
    user_totals = history_df.groupby('user_id')['play_count'].sum()
    top_users   = user_totals.nlargest(MAX_USERS).index
    history_df  = history_df[history_df['user_id'].isin(top_users)]
    log.info(f"  Top {MAX_USERS} users → {len(history_df):,} interactions")

    # 4. Chỉ giữ tracks có ít nhất 1 interaction
    active_track_ids = set(history_df['track_id'].unique())
    music_df = music_df[music_df['track_id'].isin(active_track_ids)].reset_index(drop=True)
    log.info(f"  Tracks có interaction: {len(music_df):,}")

    # 5. Tạo index mapping
    track_id_to_idx = {tid: i for i, tid in enumerate(music_df['track_id'])}
    user_ids        = list(top_users[:MAX_USERS])
    user_id_to_idx  = {uid: i for i, uid in enumerate(user_ids)}

    # 6. Build tracks.json
    log.info("Building tracks.json ...")
    audio_feats = ['danceability','energy','valence','tempo','acousticness','liveness','speechiness']
    tracks = []
    for _, row in tqdm(music_df.iterrows(), total=len(music_df), desc="Tracks"):
        t = {
            "track_id_str": str(row['track_id']),
            "title":        str(row.get('title', '')),
            "artist":       str(row.get('artist', '')),
            "genre":        genre_heuristic(row),
            # Thêm tags từ CSV nếu có
            "tags":         str(row.get('tags', '')) if pd.notna(row.get('tags','')) else '',
            "year":         int(row['year']) if pd.notna(row.get('year')) else None,
            "duration_ms":  int(row['duration_ms']) if pd.notna(row.get('duration_ms')) else None,
            "spotify_preview_url": str(row.get('spotify_preview_url','')) if pd.notna(row.get('spotify_preview_url','')) else '',
            "spotify_id":   str(row.get('spotify_id','')) if pd.notna(row.get('spotify_id','')) else '',
            "audio_features": {
                k: safe_float(row.get(k, .5)) for k in audio_feats
            },
            "content_vector": content_vector(row),
            "total_plays": 0,
            "popularity": 50,   # sẽ cập nhật sau
        }
        tracks.append(t)

    # 7. Build users.json
    log.info("Building users.json ...")
    users = []
    for i, uid in enumerate(tqdm(user_ids, desc="Users")):
        u = {
            "username":    f"user_{i:05d}",
            "role":        "user",
            "_lastfm_id":  str(uid),
            "demographics": {
                "age":      random.randint(18, 45),
                "gender":   random.choice(["male","female","other"]),
                "location": random.choice(["VN","US","UK","JP","FR","KR"]),
            },
            "onboarding_preferences": {
                "favorite_genres": random.sample(GENRES_ALL, k=random.randint(2,4)),
                "mood": random.choice(MOODS),
            },
        }
        users.append(u)

    # 8. Build interactions.json + cập nhật total_plays
    log.info("Building interactions.json ...")
    interactions = []
    for _, row in tqdm(history_df.iterrows(), total=len(history_df), desc="Interactions"):
        uid = str(row['user_id'])
        tid = str(row['track_id'])
        pc  = int(row['play_count'])

        u_idx = user_id_to_idx.get(uid)
        t_idx = track_id_to_idx.get(tid)
        if u_idx is None or t_idx is None: continue

        interactions.append({"_user_idx": u_idx, "_track_idx": t_idx, "play_count": pc})
        tracks[t_idx]['total_plays'] += pc

    # Cập nhật popularity dựa trên total_plays (normalize 0-100)
    max_plays = max((t['total_plays'] for t in tracks), default=1)
    for t in tracks:
        t['popularity'] = min(100, int(t['total_plays'] / max_plays * 100))

    # 9. Lưu file
    log.info("Saving JSON files ...")
    for fname, data in [
        ("tracks.json",       tracks),
        ("users.json",        users),
        ("interactions.json", interactions),
    ]:
        out_path = os.path.join(OUTPUT_DIR, fname)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        log.info(f"  ✅ {fname}: {len(data):,} records → {out_path}")

    log.info(f"""
=== PREPROCESSING COMPLETE ===
  Tracks       : {len(tracks):,}
  Users        : {len(users):,}
  Interactions : {len(interactions):,}
  Output dir   : {OUTPUT_DIR}/
""")


if __name__ == "__main__":
    main()
