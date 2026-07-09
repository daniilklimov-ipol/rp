"""Local HTTP server the browser extension talks to.

Endpoints
---------
GET  /health              -> server + model status
POST /predict              {"video_ids": [...]}  -> predictions for a batch of thumbnails
POST /watch                 report real watch progress for a video (from the watch page)
GET  /history?limit=N       recent watch events (for the GUI)
GET  /videos?limit=N        known videos (for the GUI)
GET  /profile               per-channel / per-category interest summary
POST /train                 force a model retrain now

The server binds to 127.0.0.1 only and enables permissive CORS so that a
content script running on youtube.com (origin `chrome-extension://<id>`) can
call it with `fetch()`.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import ingest
from .config import Settings, load_settings
from .db import Prediction, Video, WatchEvent, init_db, session_scope
from .model import WatchPredictor, recompute_interest_profile
from .youtube_api import YouTubeClient

log = logging.getLogger("ytpredictor.server")

_train_lock = threading.Lock()


class AppState:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.predictor = WatchPredictor()
        self.predictor.load()
        self._profile = None
        self._profile_dirty = True
        self._events_since_train = 0

    @property
    def client(self) -> Optional[YouTubeClient]:
        if not self.settings.youtube_api_key:
            return None
        return YouTubeClient(self.settings.youtube_api_key)

    def profile(self, session):
        if self._profile is None or self._profile_dirty:
            self._profile = recompute_interest_profile(session)
            self._profile_dirty = False
        return self._profile

    def mark_dirty(self):
        self._profile_dirty = True

    def maybe_retrain(self, session):
        self._events_since_train += 1
        if self._events_since_train < 5:
            return
        self._events_since_train = 0
        with _train_lock:
            self.predictor.train(session, min_samples=self.settings.min_training_samples)


state: AppState | None = None


# -- schemas (module-level: FastAPI needs these resolvable via get_type_hints) --
class PredictRequest(BaseModel):
    video_ids: list[str] = Field(default_factory=list, max_length=200)


class VideoPrediction(BaseModel):
    video_id: str
    title: str = ""
    percent: float
    interesting: bool
    confidence: float
    model_version: str
    error: Optional[str] = None


class PredictResponse(BaseModel):
    predictions: list[VideoPrediction]
    api_key_configured: bool


class WatchReport(BaseModel):
    video_id: str
    watched_seconds: float
    duration_seconds: float
    title: Optional[str] = None
    channel_id: Optional[str] = None
    channel_title: Optional[str] = None


def create_app(settings: Settings | None = None) -> FastAPI:
    global state
    settings = settings or load_settings()
    init_db()
    state = AppState(settings)

    app = FastAPI(title="YouTube Watch-Completion Predictor", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"chrome-extension://.*|moz-extension://.*|http://localhost(:\d+)?|http://127\.0\.0\.1(:\d+)?",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- routes -----------------------------------------------------------
    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "model_trained": state.predictor.model is not None,
            "n_samples": state.predictor.n_samples,
            "api_key_configured": bool(state.settings.youtube_api_key),
            "port": state.settings.server_port,
        }

    @app.post("/predict", response_model=PredictResponse)
    def predict(req: PredictRequest):
        if not req.video_ids:
            return PredictResponse(predictions=[], api_key_configured=bool(state.settings.youtube_api_key))

        video_ids = req.video_ids[:200]
        results: list[VideoPrediction] = []

        with session_scope() as session:
            client = state.client
            known = {v.video_id: v for v in session.query(Video).filter(Video.video_id.in_(video_ids)).all()}
            missing = [vid for vid in video_ids if vid not in known]

            if missing and client is not None:
                try:
                    ingest.ensure_videos(session, client, missing)
                    known = {
                        v.video_id: v
                        for v in session.query(Video).filter(Video.video_id.in_(video_ids)).all()
                    }
                except Exception as exc:  # noqa: BLE001 - surface as per-item error below
                    log.warning("YouTube API fetch failed: %s", exc)

            profile = state.profile(session)

            for vid in video_ids:
                video = known.get(vid)
                if video is None:
                    reason = "no_api_key" if client is None else "fetch_failed"
                    results.append(
                        VideoPrediction(
                            video_id=vid,
                            percent=profile.global_avg_percent,
                            interesting=profile.global_avg_percent >= state.settings.interesting_threshold,
                            confidence=0.1,
                            model_version="unknown",
                            error=reason,
                        )
                    )
                    continue

                result = state.predictor.predict(
                    session, video, profile, threshold=state.settings.interesting_threshold
                )
                session.add(
                    Prediction(
                        video_id=vid,
                        predicted_percent=result.percent,
                        interesting=result.interesting,
                        confidence=result.confidence,
                        model_version=result.model_version,
                    )
                )
                results.append(
                    VideoPrediction(
                        video_id=vid,
                        title=video.title,
                        percent=result.percent,
                        interesting=result.interesting,
                        confidence=result.confidence,
                        model_version=result.model_version,
                    )
                )

        return PredictResponse(predictions=results, api_key_configured=bool(state.settings.youtube_api_key))

    @app.post("/watch")
    def report_watch(report: WatchReport):
        if report.duration_seconds <= 0:
            raise HTTPException(status_code=400, detail="duration_seconds must be > 0")

        percent = max(0.0, min(100.0, 100.0 * report.watched_seconds / report.duration_seconds))

        with session_scope() as session:
            video = session.get(Video, report.video_id)
            if video is None:
                video = Video(
                    video_id=report.video_id,
                    title=report.title or "",
                    channel_id=report.channel_id or "",
                    channel_title=report.channel_title or "",
                    duration_seconds=int(report.duration_seconds),
                    fetched_at=datetime.now(timezone.utc),
                )
                client = state.client
                if client is not None:
                    try:
                        ingest.ensure_videos(session, client, [report.video_id])
                        video = session.get(Video, report.video_id) or video
                    except Exception as exc:  # noqa: BLE001
                        log.warning("YouTube API enrichment failed: %s", exc)
                session.merge(video)

            session.add(
                WatchEvent(
                    video_id=report.video_id,
                    watched_seconds=report.watched_seconds,
                    duration_seconds=report.duration_seconds,
                    percent_watched=percent,
                )
            )
            state.mark_dirty()
            state.maybe_retrain(session)

        return {"status": "recorded", "percent_watched": round(percent, 1)}

    @app.get("/history")
    def history(limit: int = 50):
        with session_scope() as session:
            rows = (
                session.query(WatchEvent, Video)
                .join(Video, Video.video_id == WatchEvent.video_id)
                .order_by(WatchEvent.watched_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "video_id": e.video_id,
                    "title": v.title,
                    "channel_title": v.channel_title,
                    "percent_watched": round(e.percent_watched, 1),
                    "watched_at": e.watched_at.isoformat() if e.watched_at else None,
                }
                for e, v in rows
            ]

    @app.get("/videos")
    def videos(limit: int = 100):
        with session_scope() as session:
            rows = session.query(Video).order_by(Video.fetched_at.desc()).limit(limit).all()
            return [
                {
                    "video_id": v.video_id,
                    "title": v.title,
                    "channel_title": v.channel_title,
                    "duration_seconds": v.duration_seconds,
                    "view_count": v.view_count,
                }
                for v in rows
            ]

    @app.get("/profile")
    def profile_summary():
        with session_scope() as session:
            profile = state.profile(session)
            return {
                "global_avg_percent": round(profile.global_avg_percent, 1),
                "channels": [
                    {"channel_id": cid, "avg_percent": round(avg, 1), "count": profile.channel_watch_count.get(cid, 0)}
                    for cid, avg in sorted(profile.channel_avg_percent.items(), key=lambda kv: -kv[1])
                ],
                "categories": [
                    {"category_id": cid, "avg_percent": round(avg, 1), "count": profile.category_watch_count.get(cid, 0)}
                    for cid, avg in sorted(profile.category_avg_percent.items(), key=lambda kv: -kv[1])
                ],
            }

    @app.post("/train")
    def train_now():
        with session_scope() as session, _train_lock:
            n = state.predictor.train(session, min_samples=state.settings.min_training_samples)
        return {
            "n_samples": n,
            "model_trained": state.predictor.model is not None,
            "min_required": state.settings.min_training_samples,
        }

    return app
