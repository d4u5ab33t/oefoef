#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dailymotion AI Video Search.
Dailymotion's search index is weak + likes are usually 0, so we use a
**view-count proxy** of 50,000 (DM videos with 50k+ views are trending).
We also fetch /videos with ?sort=trending for a baseline.
"""
import time
import csv
from datetime import datetime
from pathlib import Path

import requests

KEYWORDS = [
    "AI dance", "funny video", "AI art", "AI template", "AI Design",
    "photography", "viral AI-generated video", "CCTV", "transition",
    "klingai", "kling AI", "vidu", "vidu AI", "jimeng", "jimeng AI",
    "可灵", "即梦",
]
MIN_VIEWS = 50_000     # Dailymotion has no useful like signal in search
DELAY = 1.0
RESULTS_PER = 30

BASE = "https://api.dailymotion.com"
OUTPUT_DIR = Path(__file__).resolve().parent


def search(keyword, limit=RESULTS_PER):
    try:
        r = requests.get(
            f"{BASE}/videos",
            params={
                "search": keyword, "limit": limit, "sort": "relevance",
                "fields": "id,title,description,thumbnail_url,views_total,likes_total,owner.username,duration,created_time",
            }, timeout=20,
        )
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}")
            return []
        return r.json().get("list", []) or []
    except Exception as e:
        print(f"  exc: {e}")
        return []


def trending(limit=20):
    try:
        r = requests.get(
            f"{BASE}/videos",
            params={
                "limit": limit, "sort": "trending",
                "fields": "id,title,description,thumbnail_url,views_total,likes_total,owner.username,duration,created_time",
            }, timeout=20,
        )
        if r.status_code != 200:
            return []
        return r.json().get("list", []) or []
    except Exception:
        return []


def main():
    print("🎬 Dailymotion AI Video Search")
    print("=" * 60)

    rows = []
    seen_ids = set()

    print("\n[trending] Fetching Dailymotion trending...")
    tr = trending(20)
    print(f"  → {len(tr)} trending candidates")
    for v in tr:
        if v["id"] in seen_ids:
            continue
        likes = int(v.get("likes_total") or 0)
        views = int(v.get("views_total") or 0)
        if views < MIN_VIEWS:
            continue
        seen_ids.add(v["id"])
        rows.append({
            "tag": "[trending]", "platform": "Dailymotion",
            "cover_url": v.get("thumbnail_url", ""),
            "url": f"https://www.dailymotion.com/video/{v['id']}",
            "views": views, "likes": likes, "comments": 0,
        })

    for i, kw in enumerate(KEYWORDS, 1):
        print(f"\n[{i}/{len(KEYWORDS)}] {kw}")
        items = search(kw)
        kept = 0
        for v in items:
            if v["id"] in seen_ids:
                continue
            likes = int(v.get("likes_total") or 0)
            views = int(v.get("views_total") or 0)
            if views < MIN_VIEWS:
                continue
            seen_ids.add(v["id"])
            rows.append({
                "tag": kw, "platform": "Dailymotion",
                "cover_url": v.get("thumbnail_url", ""),
                "url": f"https://www.dailymotion.com/video/{v['id']}",
                "views": views, "likes": likes, "comments": 0,
            })
            kept += 1
        print(f"  → {len(items)} candidates, {kept} passed (views >= {MIN_VIEWS})")
        time.sleep(DELAY)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = OUTPUT_DIR / f"dailymotion_search_results_{ts}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["标签名字", "平台", "封面链接", "网页链接", "播放数", "点赞数", "评论数"])
        for r in rows:
            w.writerow([r["tag"], r["platform"], r["cover_url"], r["url"],
                        r["views"], r["likes"], r["comments"]])

    print(f"\n✅ Dailymotion search done. {len(rows)} videos kept.")
    print(f"📁 {out}")


if __name__ == "__main__":
    main()
