"""
Populates atlas.db with clearly-fictional sample data so you can see the
dashboard working before you plug in real numbers. Every artist/track name
here is a placeholder - safe to wipe with the "Reset demo data" button in
the UI (calls POST /api/reset) once you start ingesting real metrics.

Run from the project root:
    python scripts/seed_demo_data.py
"""

import os
import sys
import random
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db  # noqa: E402

random.seed(7)

DEMO_POSTS = [
    dict(platform="tiktok", external_id="demo-tt-1", track_title="Sample Track A",
         artist="Demo Artist", url="https://example.com/tiktok/demo-tt-1",
         start_views=2_000, growth="viral"),
    dict(platform="instagram", external_id="demo-ig-1", track_title="Sample Track A",
         artist="Demo Artist", url="https://example.com/instagram/demo-ig-1",
         start_views=800, growth="steady"),
    dict(platform="youtube", external_id="demo-yt-1", track_title="Sample Track B",
         artist="Demo Artist Two", url="https://example.com/youtube/demo-yt-1",
         start_views=15_000, growth="flat"),
    dict(platform="tiktok", external_id="demo-tt-2", track_title="Sample Track C",
         artist="Demo Artist Three", url="https://example.com/tiktok/demo-tt-2",
         start_views=500, growth="slow"),
]

GROWTH_CURVES = {
    "viral": 1.9,
    "steady": 1.25,
    "flat": 1.02,
    "slow": 1.08,
}


def build_snapshots(start_views, growth_key, points=8, hours_apart=6):
    multiplier = GROWTH_CURVES[growth_key]
    views = start_views
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    snaps = []
    for i in range(points):
        t = now - timedelta(hours=hours_apart * (points - i))
        jitter = random.uniform(0.95, 1.05)
        views = max(views, int(views * multiplier * jitter))
        likes = int(views * random.uniform(0.06, 0.11))
        comments = int(views * random.uniform(0.004, 0.012))
        shares = int(views * random.uniform(0.006, 0.02))
        snaps.append(
            {
                "views": views,
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "recorded_at": t.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    return snaps


def main():
    db.init_db()
    for post_def in DEMO_POSTS:
        post_id = db.upsert_post(
            platform=post_def["platform"],
            external_id=post_def["external_id"],
            track_title=post_def["track_title"],
            artist=post_def["artist"],
            url=post_def["url"],
        )
        snaps = build_snapshots(post_def["start_views"], post_def["growth"])
        for s in snaps:
            db.add_snapshot(post_id, s["views"], s["likes"], s["comments"], s["shares"],
                             recorded_at=s["recorded_at"])
        print(f"Seeded {post_def['platform']}/{post_def['external_id']} "
              f"with {len(snaps)} snapshots (final views={snaps[-1]['views']:,})")

    print("\nDone. Start the app with `python app.py` and open http://localhost:5000")
    print("Click 'Reset demo data' in the dashboard whenever you're ready to go live.")


if __name__ == "__main__":
    main()
