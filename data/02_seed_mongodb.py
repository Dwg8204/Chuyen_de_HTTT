#!/usr/bin/env python3
"""
02_seed_mongodb.py - Seed processed JSON data vào MongoDB
"""
import json, os, random
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient, ASCENDING, TEXT
from tqdm import tqdm
from dotenv import load_dotenv
import bcrypt

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("DB_NAME",   "musicrec")
PROCESSED = "processed"

def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ping')
    print(f"✅ Connected to MongoDB: {MONGO_URI}")
    return client[DB_NAME]

def create_indexes(db):
    print("Creating indexes …")
    db.tracks.create_index([("title", TEXT), ("artist", TEXT)])
    db.tracks.create_index([("genre", ASCENDING)])
    db.tracks.create_index([("total_plays", ASCENDING)])
    db.tracks.create_index("track_id_str", unique=True)
    db.users.create_index("username", unique=True)
    db.interactions.create_index([("user_id", ASCENDING), ("track_id", ASCENDING)], unique=True)
    db.interactions.create_index("user_id")
    db.interactions.create_index("track_id")
    print("✅ Indexes created")

def seed_tracks(db) -> list:
    print("Seeding tracks …")
    with open(f"{PROCESSED}/tracks.json", encoding='utf-8') as f:
        tracks = json.load(f)
    db.tracks.drop()
    ids = []
    for i in tqdm(range(0, len(tracks), 1000), desc="Tracks"):
        r = db.tracks.insert_many(tracks[i:i+1000])
        ids.extend(r.inserted_ids)
    print(f"✅ Inserted {len(ids)} tracks")
    return ids

def seed_users(db) -> list:
    print("Seeding users …")
    with open(f"{PROCESSED}/users.json", encoding='utf-8') as f:
        raw_users = json.load(f)
    db.users.drop()

    default_pw = bcrypt.hashpw(b"password123", bcrypt.gensalt()).decode()
    docs = []
    for u in raw_users:
        docs.append({
            "username": u["username"],
            "password": default_pw,
            "role":     "user",
            "demographics":            u["demographics"],
            "onboarding_preferences":  u["onboarding_preferences"],
            "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 365)),
        })

    ids = []
    for i in tqdm(range(0, len(docs), 500), desc="Users"):
        try:
            r = db.users.insert_many(docs[i:i+500], ordered=False)
            ids.extend(r.inserted_ids)
        except Exception:
            pass
    print(f"✅ Inserted {len(ids)} users")
    return ids

def seed_admin(db):
    print("Seeding admin account …")
    pw = bcrypt.hashpw(b"Admin@123", bcrypt.gensalt()).decode()
    admin = {
        "username": "admin",
        "password": pw,
        "role": "admin",
        "demographics": {"age": 25, "gender": "other", "location": "VN"},
        "onboarding_preferences": {"favorite_genres": ["pop","rock","electronic"], "mood": "energetic"},
        "created_at": datetime.now(timezone.utc),
    }
    try:
        db.users.insert_one(admin)
        print("✅ Admin created  →  username: admin  |  password: Admin@123")
    except Exception:
        print("ℹ️  Admin already exists, skipping")

def seed_interactions(db, track_ids: list, user_ids: list):
    print("Seeding interactions …")
    with open(f"{PROCESSED}/interactions.json", encoding='utf-8') as f:
        raw = json.load(f)
    db.interactions.drop()

    docs = []
    now = datetime.now(timezone.utc)
    for item in raw:
        u_idx = item["_user_idx"]
        t_idx = item["_track_idx"]
        if u_idx >= len(user_ids) or t_idx >= len(track_ids):
            continue
        docs.append({
            "user_id":     user_ids[u_idx],
            "track_id":    track_ids[t_idx],
            "play_count":  item["play_count"],
            "last_played": now - timedelta(days=random.randint(0, 180)),
        })

    inserted = 0
    for i in tqdm(range(0, len(docs), 2000), desc="Interactions"):
        try:
            r = db.interactions.insert_many(docs[i:i+2000], ordered=False)
            inserted += len(r.inserted_ids)
        except Exception:
            pass
    print(f"✅ Inserted {inserted} interactions")

def main():
    db = get_db()
    create_indexes(db)
    track_ids = seed_tracks(db)
    user_ids  = seed_users(db)
    seed_admin(db)
    seed_interactions(db, track_ids, user_ids)

    print(f"""
╔══════════════════════════════════╗
║      SEEDING COMPLETE ✅         ║
╠══════════════════════════════════╣
║  Tracks:       {db.tracks.count_documents({}):>8,}         ║
║  Users:        {db.users.count_documents({}):>8,}         ║
║  Interactions: {db.interactions.count_documents({}):>8,}         ║
╚══════════════════════════════════╝
""")

if __name__ == "__main__":
    main()
