"""
Atlas Monitor - Flask app
---------------------------
Run with:  python app.py
Then open  http://localhost:5000

This app does NOT talk to TikTok, Instagram, or YouTube itself. You feed
it real numbers - by hand, by a spreadsheet import you write, or by a
script that calls the official platform APIs on your own credentials -
via POST /api/ingest. It stores every reading and computes a Viral Score
from what you've actually given it. See README.md for the full API docs.
"""

from flask import Flask, request, jsonify, render_template
import db
from viral_score import compute_viral_score

app = Flask(__name__)
db.init_db()


# ---------------------------------------------------------------- pages ---

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# ------------------------------------------------------------- read API ---

@app.route("/api/posts")
def api_posts():
    rows = db.list_posts_with_latest()
    out = []
    for row in rows:
        post = row["post"]
        snaps = row["recent_snapshots"]
        scoring = compute_viral_score(snaps)
        latest = snaps[0] if snaps else None
        out.append(
            {
                "id": post["id"],
                "platform": post["platform"],
                "external_id": post["external_id"],
                "track_title": post["track_title"],
                "artist": post["artist"],
                "url": post["url"],
                "latest": latest,
                "viral_score": scoring,
            }
        )
    out.sort(key=lambda p: p["viral_score"]["score"], reverse=True)
    return jsonify(out)


@app.route("/api/posts/<int:post_id>/history")
def api_post_history(post_id):
    history = db.get_post_history(post_id)
    if history is None:
        return jsonify({"error": "not found"}), 404

    snaps = history["snapshots"]
    scored_points = []
    for i, snap in enumerate(snaps):
        window = [snap] if i == 0 else [snap, snaps[i - 1]]
        window = list(reversed(window))  # most recent first, matches compute_viral_score
        scoring = compute_viral_score(window)
        scored_points.append({**snap, "viral_score": scoring["score"]})

    return jsonify({"post": history["post"], "snapshots": scored_points})


@app.route("/api/summary")
def api_summary():
    rows = db.list_posts_with_latest()
    by_platform = {}
    total_views = 0
    total_engagement_actions = 0
    scored = []

    for row in rows:
        post = row["post"]
        snaps = row["recent_snapshots"]
        if not snaps:
            continue
        latest = snaps[0]
        plat = post["platform"]
        by_platform.setdefault(plat, {"views": 0, "posts": 0})
        by_platform[plat]["views"] += latest["views"]
        by_platform[plat]["posts"] += 1
        total_views += latest["views"]
        total_engagement_actions += latest["likes"] + latest["comments"] + latest["shares"]
        scored.append(compute_viral_score(snaps)["score"])

    avg_score = round(sum(scored) / len(scored), 1) if scored else 0.0

    return jsonify(
        {
            "total_views": total_views,
            "total_posts": len(rows),
            "total_engagement_actions": total_engagement_actions,
            "average_viral_score": avg_score,
            "by_platform": by_platform,
        }
    )


# ------------------------------------------------------------ write API ---

@app.route("/api/ingest", methods=["POST"])
def api_ingest():
    """
    Body (JSON):
    {
      "platform": "tiktok" | "instagram" | "youtube" | ...,
      "external_id": "the post/video id on that platform",
      "track_title": "optional",
      "artist": "optional",
      "url": "optional",
      "views": 12345,
      "likes": 678,
      "comments": 90,
      "shares": 12,
      "recorded_at": "optional ISO timestamp, defaults to now"
    }

    Call this once per post every time you check its stats. Each call
    adds a new snapshot; it does not overwrite history.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "expected JSON body"}), 400

    required = ["platform", "external_id"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"missing required fields: {missing}"}), 400

    try:
        views = int(data.get("views", 0))
        likes = int(data.get("likes", 0))
        comments = int(data.get("comments", 0))
        shares = int(data.get("shares", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "views/likes/comments/shares must be integers"}), 400

    if min(views, likes, comments, shares) < 0:
        return jsonify({"error": "metrics cannot be negative"}), 400

    post_id = db.upsert_post(
        platform=data["platform"],
        external_id=str(data["external_id"]),
        track_title=data.get("track_title"),
        artist=data.get("artist"),
        url=data.get("url"),
    )
    db.add_snapshot(
        post_id, views, likes, comments, shares, recorded_at=data.get("recorded_at")
    )

    return jsonify({"status": "ok", "post_id": post_id}), 201


@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Wipes all data. Intended for clearing demo/seed data before you
    start feeding in real numbers."""
    db.delete_all_demo_data()
    return jsonify({"status": "cleared"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
