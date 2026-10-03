"""
Atlas Monitor - Viral Score
----------------------------
This is a transparent heuristic, not a trained model or a claim about how
any platform's own algorithm works. It combines three things that are
actually visible in public metrics:

1. ENGAGEMENT  - how much people who saw it did something about it.
   engagement_rate = (likes + 2*comments + 3*shares) / views
   Comments and shares are weighted higher than likes because they take
   more effort and (for shares especially) extend reach.

2. VELOCITY    - how fast views are growing right now, per hour, between
   the two most recent snapshots you ingested. A post with 1M views that
   has been flat for a week scores lower here than one that just went
   from 10k to 100k in a day.

3. SCALE       - raw reach (total views), log-scaled so a jump from
   1k -> 10k views moves the needle as much as 100k -> 1M.

Each component is squashed to 0-100 with a log curve against a reference
point (REFERENCE_*), then combined with fixed weights into a single
0-100 score. The reference points are just reasonable defaults for
short-form music/video content - edit them for your own catalogue size.

This is deliberately simple and inspectable: given the same two
snapshots, you can recompute the score by hand.
"""

import math

WEIGHT_ENGAGEMENT = 0.40
WEIGHT_VELOCITY = 0.35
WEIGHT_SCALE = 0.25

# Reference points used to normalize each raw component onto a 0-100 curve.
# These represent "this value maps to roughly 100 points" - tune them to
# whatever counts as a genuine hit for your catalogue.
REFERENCE_ENGAGEMENT_RATE = 0.12   # 12% weighted engagement = full marks
REFERENCE_VIEWS_PER_HOUR = 50_000  # 50k views/hour sustained = full marks
REFERENCE_TOTAL_VIEWS = 5_000_000  # 5M total views = full marks


def _log_scale(value, reference):
    """Map value in [0, inf) to [0, 100] using a log curve, saturating
    smoothly rather than hard-clipping."""
    if value <= 0:
        return 0.0
    score = 100 * math.log1p(value) / math.log1p(reference)
    return max(0.0, min(100.0, score))


def engagement_component(views, likes, comments, shares):
    if views <= 0:
        return 0.0
    weighted_actions = likes + 2 * comments + 3 * shares
    rate = weighted_actions / views
    return min(100.0, 100 * rate / REFERENCE_ENGAGEMENT_RATE)


def velocity_component(prev_snapshot, latest_snapshot):
    """views/hour between two snapshots. Returns 0 if we don't have two
    points yet, or if the clock didn't actually move forward."""
    if not prev_snapshot or not latest_snapshot:
        return 0.0
    from datetime import datetime

    fmt_variants = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")

    def parse(ts):
        for fmt in fmt_variants:
            try:
                return datetime.strptime(ts, fmt)
            except ValueError:
                continue
        return datetime.fromisoformat(ts)

    t0 = parse(prev_snapshot["recorded_at"])
    t1 = parse(latest_snapshot["recorded_at"])
    hours = (t1 - t0).total_seconds() / 3600.0
    if hours <= 0:
        return 0.0

    delta_views = latest_snapshot["views"] - prev_snapshot["views"]
    if delta_views <= 0:
        return 0.0

    views_per_hour = delta_views / hours
    return _log_scale(views_per_hour, REFERENCE_VIEWS_PER_HOUR)


def scale_component(views):
    return _log_scale(views, REFERENCE_TOTAL_VIEWS)


def compute_viral_score(recent_snapshots):
    """recent_snapshots: list of up to 2 snapshot dicts, most recent first
    (as returned by db.list_posts_with_latest). Returns a dict with the
    overall score and its components, so the UI can show its work."""
    if not recent_snapshots:
        return {
            "score": 0.0,
            "engagement": 0.0,
            "velocity": 0.0,
            "scale": 0.0,
            "has_velocity_data": False,
        }

    latest = recent_snapshots[0]
    prev = recent_snapshots[1] if len(recent_snapshots) > 1 else None

    eng = engagement_component(
        latest["views"], latest["likes"], latest["comments"], latest["shares"]
    )
    vel = velocity_component(prev, latest)
    scale = scale_component(latest["views"])

    score = (
        WEIGHT_ENGAGEMENT * eng + WEIGHT_VELOCITY * vel + WEIGHT_SCALE * scale
    )

    return {
        "score": round(score, 1),
        "engagement": round(eng, 1),
        "velocity": round(vel, 1),
        "scale": round(scale, 1),
        "has_velocity_data": prev is not None,
    }
