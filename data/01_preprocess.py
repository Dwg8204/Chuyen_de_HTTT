#!/usr/bin/env python3
"""
01_preprocess.py - Tiền xử lý và fuzzy join 2 datasets
"""
import os, re, json, random, logging
import pandas as pd
import numpy as np
from rapidfuzz import process, fuzz
from unidecode import unidecode
from tqdm import tqdm

# ─── Config ────────────────────────────────────────────────────────────────────
SPOTIFY_FILE   = "raw/spotify_tracks.csv"
LASTFM_FILE    = "raw/lastfm_interactions.tsv"
OUTPUT_DIR     = "processed"
FUZZY_THRESHOLD = 90
MAX_TRACKS     = 50_000
MAX_USERS      = 5_000
MIN_PLAYS      = 2
RANDOM_SEED    = 42

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Helpers ───────────────────────────────────────────────────────────────────
def norm(text: str) -> str:
    if not isinstance(text, str): return ""
    t = unidecode(text.lower().strip())
    t = re.sub(r'\s*(feat\.?|ft\.?|featuring)\s+.*', '', t, flags=re.I)
    t = re.sub(r'[^\w\s]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

def parse_artist(val) -> str:
    if isinstance(val, list): return val[0] if val else ""
    s = str(val)
    if s.startswith('['):
        try: return eval(s)[0]
        except: pass
    return s.split(',')[0].strip()

def genre_heuristic(r) -> list:
    d = float(r.get('danceability', .5))
    e = float(r.get('energy', .5))
    v = float(r.get('valence', .5))
    a = float(r.get('acousticness', .5))
    sp = float(r.get('speechiness', .5))
    tags = []
    if d > .7 and e > .6:              tags.append('pop')
    if e > .8 and v < .4:             tags.append('rock')
    if d > .75 and sp > .1:           tags.append('rnb')
    if a > .6 and e < .5:             tags.append('indie')
    if a > .7:                         tags.append('acoustic')
    if sp > .3:                        tags.append('hiphop')
    if e < .4 and v > .5:             tags.append('jazz')
    if e > .85:                        tags.append('electronic')
    return tags or ['pop']

def content_vector(r) -> list:
    return [
        float(r.get('danceability',  .5)),
        float(r.get('energy',        .5)),
        float(r.get('valence',       .5)),
        float(r.get('tempo',       120)) / 250.0,
        float(r.get('acousticness',  .5)),
        float(r.get('liveness',      .5)),
        float(r.get('speechiness',   .5)),
    ]

# ─── Load Spotify ──────────────────────────────────────────────────────────────
def load_spotify() -> pd.DataFrame:
    log.info("Loading Spotify dataset …")
    if not os.path.exists(SPOTIFY_FILE):
        raise FileNotFoundError(f"{SPOTIFY_FILE} not found. See README_DATA.md")
    df = pd.read_csv(SPOTIFY_FILE)
    log.info(f"  Raw rows: {len(df)}, cols: {list(df.columns)}")

    # Auto-detect columns
    title_col  = next((c for c in ['name','title','track_name','song_name']   if c in df.columns), None)
    artist_col = next((c for c in ['artists','artist','artist_name']          if c in df.columns), None)
    id_col     = next((c for c in ['id','track_id','spotify_id']              if c in df.columns), None)
    pop_col    = next((c for c in ['popularity','pop']                        if c in df.columns), None)

    if not title_col or not artist_col:
        raise ValueError(f"Cannot detect title/artist columns. Available: {list(df.columns)}")

    df = df.rename(columns={title_col: 'title', artist_col: 'artist'})
    if id_col and id_col != 'id':    df = df.rename(columns={id_col: 'id'})
    if pop_col and pop_col != 'popularity': df = df.rename(columns={pop_col: 'popularity'})

    df['artist'] = df['artist'].apply(parse_artist)

    for feat in ['danceability','energy','valence','tempo','acousticness','liveness','speechiness']:
        if feat not in df.columns: df[feat] = 0.5
    if 'popularity' not in df.columns: df['popularity'] = 50
    if 'id'         not in df.columns: df['id'] = [f"sp_{i}" for i in range(len(df))]

    df = df.dropna(subset=['title','artist'])
    df = df[df['title'].str.strip() != '']
    df['_key'] = df['artist'].apply(norm) + '|||' + df['title'].apply(norm)
    df = df.drop_duplicates(subset=['_key'])
    log.info(f"  After cleaning: {len(df)} tracks")
    return df

# ─── Load Last.fm ──────────────────────────────────────────────────────────────
def load_lastfm() -> pd.DataFrame | None:
    log.info("Loading Last.fm dataset …")
    if not os.path.exists(LASTFM_FILE):
        log.warning(f"{LASTFM_FILE} not found – will generate synthetic interactions")
        return None

    for sep in ['\t', ',']:
        try:
            df = pd.read_csv(LASTFM_FILE, sep=sep, on_bad_lines='skip',
                             encoding='utf-8', encoding_errors='replace')
            break
        except Exception as e:
            log.warning(f"  sep='{sep}' failed: {e}")
            df = None
    if df is None: return None

    log.info(f"  Raw rows: {len(df)}, cols: {list(df.columns)}")

    user_col  = next((c for c in ['user_id','user','userid']                     if c in df.columns), None)
    artist_col= next((c for c in ['artist_name','artist','artistname']            if c in df.columns), None)
    track_col = next((c for c in ['track_name','track','trackname','song']        if c in df.columns), None)
    play_col  = next((c for c in ['play_count','plays','count','playcount']       if c in df.columns), None)

    if not user_col or not artist_col or not track_col:
        log.warning("  Missing user/artist/track column – generating synthetic data")
        return None

    df = df.rename(columns={user_col:'user', artist_col:'artist', track_col:'track'})
    if play_col and play_col != 'plays': df = df.rename(columns={play_col:'plays'})
    if 'plays' not in df.columns: df['plays'] = 1

    df['plays'] = pd.to_numeric(df['plays'], errors='coerce').fillna(1).clip(lower=1).astype(int)
    df = df.dropna(subset=['user','artist','track'])
    df = df[df['plays'] >= MIN_PLAYS]

    df['_norm_artist'] = df['artist'].apply(norm)
    df['_norm_track']  = df['track'].apply(norm)
    df['_key']         = df['_norm_artist'] + '|||' + df['_norm_track']

    df = df.groupby(['user','_key']).agg(plays=('plays','sum')).reset_index()

    # Keep top MAX_USERS most-active users
    top_users = df.groupby('user')['plays'].sum().nlargest(MAX_USERS).index
    df = df[df['user'].isin(top_users)]
    log.info(f"  After filtering: {len(df)} rows, {df['user'].nunique()} users")
    return df

# ─── Fuzzy Match ───────────────────────────────────────────────────────────────
def fuzzy_join(spotify_df: pd.DataFrame, lastfm_df: pd.DataFrame) -> dict:
    sp_keys = spotify_df['_key'].tolist()
    sp_key_set = set(sp_keys)
    fm_unique = lastfm_df['_key'].unique()
    log.info(f"Fuzzy matching {len(fm_unique)} Last.fm keys → {len(sp_keys)} Spotify keys …")

    mapping = {}
    unmatched = []
    for fk in tqdm(fm_unique, desc="Matching"):
        if fk in sp_key_set:
            mapping[fk] = fk
            continue
        res = process.extractOne(fk, sp_keys, scorer=fuzz.token_sort_ratio, score_cutoff=FUZZY_THRESHOLD)
        if res:
            mapping[fk] = res[0]
        else:
            unmatched.append(fk)

    log.info(f"  Matched {len(mapping)}/{len(fm_unique)} ({len(mapping)/len(fm_unique)*100:.1f}%)")
    with open(f"{OUTPUT_DIR}/unmatched_report.txt", "w", encoding='utf-8') as f:
        f.write(f"Unmatched: {len(unmatched)}\n\n" + "\n".join(unmatched[:500]))
    return mapping

# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    spotify_df = load_spotify()
    lastfm_df  = load_lastfm()

    # ── Build track list ──────────────────────────────────────────────────────
    GENRES_ALL = ['pop','rock','rnb','indie','acoustic','hiphop','jazz','electronic']
    MOODS      = ['energetic','chill','happy','melancholic','focused']

    mapping = {}
    if lastfm_df is not None:
        mapping = fuzzy_join(spotify_df, lastfm_df)
        matched_sp_keys = set(mapping.values())
        matched   = spotify_df[spotify_df['_key'].isin(matched_sp_keys)]
        unmatched_sp = spotify_df[~spotify_df['_key'].isin(matched_sp_keys)].sort_values('popularity', ascending=False)
        extra = unmatched_sp.head(max(0, MAX_TRACKS - len(matched)))
        final_sp = pd.concat([matched, extra]).head(MAX_TRACKS).reset_index(drop=True)
    else:
        final_sp = spotify_df.sort_values('popularity', ascending=False).head(MAX_TRACKS).reset_index(drop=True)

    log.info(f"Building {len(final_sp)} track documents …")
    tracks = []
    key_to_idx = {}
    for i, row in tqdm(final_sp.iterrows(), total=len(final_sp), desc="Tracks"):
        t = {
            "track_id_str": str(row.get('id', f"sp_{i}")),
            "title":  str(row['title']),
            "artist": str(row['artist']),
            "genre":  genre_heuristic(row),
            "audio_features": {k: float(row.get(k, .5)) for k in
                               ['danceability','energy','valence','tempo','acousticness','liveness','speechiness']},
            "content_vector": content_vector(row),
            "total_plays": 0,
            "popularity": int(row.get('popularity', 50)),
        }
        tracks.append(t)
        key_to_idx[row['_key']] = i

    # ── Build user list ───────────────────────────────────────────────────────
    if lastfm_df is not None:
        unique_users = list(lastfm_df['user'].unique())[:MAX_USERS]
    else:
        unique_users = [f"lfm_user_{i}" for i in range(MAX_USERS)]

    log.info(f"Building {len(unique_users)} user documents …")
    users = []
    user_lfm_to_idx = {}
    for i, uid in enumerate(unique_users):
        username = re.sub(r'[^a-zA-Z0-9_]', '_', str(uid))[:20]
        u = {
            "username": username or f"user_{i}",
            "role": "user",
            "_lastfm_id": str(uid),
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
        user_lfm_to_idx[str(uid)] = i

    # ── Build interactions ────────────────────────────────────────────────────
    log.info("Building interactions …")
    interactions = []

    if lastfm_df is not None and mapping:
        for _, row in tqdm(lastfm_df.iterrows(), total=len(lastfm_df), desc="Interactions"):
            sp_key = mapping.get(row['_key'])
            if sp_key is None: continue
            t_idx = key_to_idx.get(sp_key)
            u_idx = user_lfm_to_idx.get(str(row['user']))
            if t_idx is None or u_idx is None: continue
            pc = int(row['plays'])
            interactions.append({"_user_idx": u_idx, "_track_idx": t_idx, "play_count": pc})
            tracks[t_idx]['total_plays'] += pc
    else:
        log.info("Generating synthetic interactions …")
        n_tracks = len(tracks)
        for u_idx, user in enumerate(tqdm(users, desc="Synthetic")):
            fav_genres = user['onboarding_preferences']['favorite_genres']
            cand = [i for i,t in enumerate(tracks) if any(g in t['genre'] for g in fav_genres)]
            if not cand: cand = list(range(n_tracks))
            weights = [tracks[i]['popularity']+1 for i in cand]
            s = sum(weights); weights = [w/s for w in weights]
            n = random.randint(30, 100)
            chosen = random.choices(cand, weights=weights, k=min(n, len(cand)))
            bucket = {}
            for ti in chosen: bucket[ti] = bucket.get(ti, 0) + random.randint(1, 5)
            for ti, pc in bucket.items():
                interactions.append({"_user_idx": u_idx, "_track_idx": ti, "play_count": pc})
                tracks[ti]['total_plays'] += pc

    # ── Save ──────────────────────────────────────────────────────────────────
    log.info("Saving JSON files …")
    for fname, data in [("tracks.json", tracks), ("users.json", users), ("interactions.json", interactions)]:
        with open(f"{OUTPUT_DIR}/{fname}", "w", encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        log.info(f"  {fname}: {len(data)} records")

    log.info(f"""
=== PREPROCESSING COMPLETE ===
  Tracks       : {len(tracks):,}
  Users        : {len(users):,}
  Interactions : {len(interactions):,}
  Output dir   : {OUTPUT_DIR}/
""")

if __name__ == "__main__":
    main()
