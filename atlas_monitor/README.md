# Atlas Monitor

A small, real, self-hosted dashboard for tracking how your posts are doing
across platforms and scoring them with a transparent "Viral Score."

**What this is not:** it does not connect to TikTok, Instagram, or YouTube
on its own, and it cannot pull your stats automatically. There is no
scraper and no background job. Every number you see in the dashboard is a
number you (or a script you write) explicitly sent it.

## Why it works this way

TikTok, Instagram, and YouTube don't offer a public, ToS-compliant way for
a random script to log into your account and pull private analytics
automatically. Building that would mean either scraping (against their
terms, and fragile) or using their *official* analytics/data APIs, which
require you to register a developer app, get it approved, and authenticate
as yourself. That's real, legitimate work you can absolutely do — Atlas
Monitor is designed to sit downstream of it: once you have numbers, from
wherever, this is where you track them over time and see which ones are
actually taking off.

In practice that means:
- Copy the numbers from each platform's own creator/analytics dashboard
  periodically, and paste them into the "Log a metrics reading" form, or
- Write a small script against the official TikTok Display API / Instagram
  Graph API / YouTube Data API (using your own developer credentials) that
  calls `POST /api/ingest` with what it finds.

## Running it

```bash
cd atlas_monitor
python -m venv venv && source venv/bin/activate      # optional but recommended
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

To see it with sample data first:

```bash
python scripts/seed_demo_data.py
```

All sample posts are clearly labeled "Demo" / "Sample" — click **Reset
demo data** in the dashboard (or `POST /api/reset`) to wipe them once
you start logging real numbers.

## API

### `POST /api/ingest`

Log one reading for one post. Call it again later for the same
`platform` + `external_id` to add another point in time — it never
overwrites history, so the dashboard can show trends and velocity.

```bash
curl -X POST http://localhost:5000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "tiktok",
    "external_id": "7284001122334455",
    "track_title": "Night Drive",
    "artist": "Your Artist Name",
    "url": "https://www.tiktok.com/@you/video/7284001122334455",
    "views": 148302,
    "likes": 12980,
    "comments": 431,
    "shares": 902
  }'
```

Required fields: `platform`, `external_id`. Everything else is optional
(`views`/`likes`/`comments`/`shares` default to 0).

### `GET /api/posts`
All tracked posts with their latest snapshot and current Viral Score,
sorted highest score first.

### `GET /api/posts/<id>/history`
Full snapshot history for one post, each point scored so you can plot a
trend.

### `GET /api/summary`
Aggregate totals across everything you've logged: total views, total
posts, total engagement actions, average Viral Score, and a breakdown by
platform.

### `POST /api/reset`
Deletes everything. Used to clear demo data — there's no undo, so be sure
before you call it against real data.

## The Viral Score

Full formula and reasoning is documented in `viral_score.py`. Short
version: it combines three things computed straight from the numbers you
give it —

- **Engagement** — `(likes + 2×comments + 3×shares) / views`
- **Velocity** — views gained per hour between your two most recent
  readings for that post
- **Scale** — total views, log-scaled so growth from 1k→10k counts as
  much as 100k→1M

— weighted 40/35/25 and combined into one 0–100 number. It's a heuristic
for spotting what's moving, not a claim about any platform's internal
ranking algorithm. The reference constants at the top of `viral_score.py`
assume short-form music/video content; tune them for your own catalogue.

## Files

```
atlas_monitor/
├── app.py                    Flask app: pages + API routes
├── db.py                     SQLite schema and data access
├── viral_score.py            The scoring formula, documented inline
├── requirements.txt
├── scripts/
│   └── seed_demo_data.py     Optional: populate with fake sample data
├── templates/
│   └── dashboard.html
└── static/
    ├── style.css
    └── dashboard.js
```

Data lives in `atlas.db` (SQLite), created automatically on first run.
