# YouTube Watch-Completion Predictor — Desktop App

A Windows desktop app that collects YouTube video metadata/comments, records
your *actual* watch history (reported by the companion [browser
extension](../extension)), stores everything in a local SQLite database, and
trains a gradient-boosting model that predicts what percentage of a new video
you're likely to watch. It exposes this as a local HTTP server the extension
queries for every thumbnail on screen.

> **Important, honest caveat:** the YouTube Data API does not expose a
> user's personal watch history or per-video watch duration (that data isn't
> public, for privacy reasons). This app gets real watch data instead by
> having the browser extension watch the `<video>` element on
> `youtube.com/watch` pages and report the furthest playback position reached
> back to `POST /watch`. No OAuth or Google sign-in is required or performed.

## How it works

```
┌─────────────────────┐        YouTube Data API v3        ┌──────────────┐
│  YouTubeWatchPredictor│ ─────────────────────────────────▶│   YouTube    │
│        .exe          │◀───────────────────────────────── │  (metadata,  │
│                       │        title/views/comments        │  comments)   │
│  ┌─────────────────┐ │                                    └──────────────┘
│  │ SQLite DB        │ │
│  │ - videos          │ │
│  │ - comments+sentiment│
│  │ - watch_events     │ │
│  │ - predictions      │ │
│  └─────────────────┘ │
│  ┌─────────────────┐ │        HTTP (localhost:8765)      ┌──────────────┐
│  │ Gradient boosting │◀───────────────────────────────── │  Browser      │
│  │ model (sklearn)    │ ─────────────────────────────────▶│  extension    │
│  └─────────────────┘ │      predictions / watch reports   └──────────────┘
└─────────────────────┘
```

## Setup

1. Get a free **YouTube Data API v3** key: [Google Cloud Console](https://console.cloud.google.com/)
   → APIs & Services → enable "YouTube Data API v3" → Credentials → Create API key.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run it:
   ```bash
   python main.py              # GUI + local server
   python main.py --headless   # local server only (no window), e.g. for autostart
   ```
4. In the **Settings** tab, paste your API key and save (this restarts the
   local server). The server listens on `http://127.0.0.1:8765` by default.
5. Install the [browser extension](../extension) and browse YouTube — as you
   scroll, it asks this server for predictions; as you watch videos, it
   reports real completion data back, which feeds the model.

## Data model (SQLite)

| Table              | Purpose                                                        |
|---------------------|-----------------------------------------------------------------|
| `videos`            | Title, channel, duration, publish date, views/likes/comments   |
| `comments`          | Top comments per video + VADER sentiment score                  |
| `watch_events`      | Real watch sessions reported by the extension (ground truth)    |
| `predictions`       | Cached model predictions per video                               |
| `channel_interest`  | Rolling avg. % watched per channel (derived)                    |
| `category_interest` | Rolling avg. % watched per YouTube category (derived)            |

The DB file lives at `%APPDATA%\YouTubeWatchPredictor\ytpredictor.db` on
Windows (see `ytpredictor/paths.py` for other platforms).

## The prediction model

- **Features**: video duration, view/like/comment ratios, comment sentiment
  (VADER: average + positive/negative ratio), days since publish, title
  length, whether it's a Short, and — the most predictive part — your
  historical average completion % for that video's *channel* and *category*.
- **Model**: `sklearn.ensemble.GradientBoostingRegressor`, trained on your
  `watch_events`, target = percent of the video actually watched.
- **Cold start**: until you've logged at least `min_training_samples`
  (default 15) watch events, predictions fall back to a heuristic — your
  channel/category average completion, or 50% if there's no history at all —
  since a model trained on a handful of rows performs worse than that
  heuristic.
- Retraining happens automatically every 5 new watch events, or on demand via
  the **"Train model now"** button / `POST /train`.

## HTTP API (consumed by the extension)

| Method | Path        | Purpose                                             |
|--------|-------------|------------------------------------------------------|
| GET    | `/health`   | Server + model status                                |
| POST   | `/predict`  | `{"video_ids": [...]}` → predictions for a batch      |
| POST   | `/watch`    | Report real watch progress for one video              |
| GET    | `/history`  | Recent watch events                                    |
| GET    | `/videos`   | Known videos                                            |
| GET    | `/profile`  | Per-channel / per-category completion averages         |
| POST   | `/train`    | Force a retrain now                                     |

Interactive docs are served at `/docs` while the app is running.

## Building the .exe (Windows)

```bat
build.bat
```

This installs dependencies + PyInstaller and produces
`dist\YouTubeWatchPredictor.exe` (uses `ytpredictor.spec`). A GitHub Actions
workflow (`.github/workflows/build-desktop-exe.yml`) does the same on every
push to this branch and uploads the `.exe` as a build artifact.

## Running the tests

```bash
pip install -r requirements.txt pytest
pytest
```

## Project layout

```
main.py                 # entrypoint: GUI (default) or --headless server
ytpredictor/
  paths.py               # per-user app-data locations (DB, model, config)
  config.py               # JSON-backed settings (API key, port, threshold)
  db.py                    # SQLAlchemy models + session management
  youtube_api.py            # YouTube Data API v3 client
  sentiment.py               # VADER comment sentiment scoring
  ingest.py                   # fetch + persist video metadata/comments
  features.py                  # feature engineering
  model.py                      # training + prediction (GradientBoostingRegressor)
  server.py                      # FastAPI app (the HTTP API above)
  runtime.py                      # runs the server in a background thread
  gui.py                            # Tkinter GUI
tests/                                # pytest suite
```
