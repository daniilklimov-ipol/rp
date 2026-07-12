"""Watch-completion prediction model.

Uses scikit-learn's GradientBoostingRegressor to predict what percentage of a
new video the user will watch, based on video attributes (duration, views,
comment sentiment, ...) and the user's own interest profile (per-channel and
per-category historical completion rates, derived from real watch history
recorded by the browser extension).

Falls back to a simple heuristic (channel/category average, or a flat 50%)
until there is enough watch history to fit a model, since a boosting model
trained on a handful of rows is worse than the heuristic it would replace.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import sentiment
from .db import Comment, Video, WatchEvent, ChannelInterest, CategoryInterest
from .features import FEATURE_NAMES, InterestProfile, build_feature_row, row_to_vector
from .paths import model_path

MODEL_VERSION = "gbr-v1"


def _video_sentiment(session: Session, video_id: str) -> tuple[float, float, float]:
    scores = [row[0] for row in session.query(Comment.sentiment).filter(Comment.video_id == video_id).all()]
    summary = sentiment.summarize(scores)
    return summary.average, summary.positive_ratio, summary.negative_ratio


def recompute_interest_profile(session: Session) -> InterestProfile:
    """Aggregate real watch history into per-channel/category averages.

    Also upserts the ChannelInterest / CategoryInterest tables so the GUI can
    show "you tend to finish 80% of videos from channel X" without redoing
    this query.
    """
    rows = (
        session.query(WatchEvent.percent_watched, Video.channel_id, Video.channel_title, Video.category_id)
        .join(Video, Video.video_id == WatchEvent.video_id)
        .all()
    )

    if not rows:
        return InterestProfile(global_avg_percent=50.0)

    global_avg = sum(r[0] for r in rows) / len(rows)

    channel_sum: dict[str, float] = {}
    channel_n: dict[str, int] = {}
    channel_title: dict[str, str] = {}
    category_sum: dict[str, float] = {}
    category_n: dict[str, int] = {}

    for percent, channel_id, ch_title, category_id in rows:
        if channel_id:
            channel_sum[channel_id] = channel_sum.get(channel_id, 0.0) + percent
            channel_n[channel_id] = channel_n.get(channel_id, 0) + 1
            channel_title[channel_id] = ch_title or channel_title.get(channel_id, "")
        if category_id:
            category_sum[category_id] = category_sum.get(category_id, 0.0) + percent
            category_n[category_id] = category_n.get(category_id, 0) + 1

    channel_avg = {cid: channel_sum[cid] / channel_n[cid] for cid in channel_sum}
    category_avg = {cid: category_sum[cid] / category_n[cid] for cid in category_sum}

    for cid, avg in channel_avg.items():
        session.merge(
            ChannelInterest(
                channel_id=cid,
                channel_title=channel_title.get(cid, ""),
                avg_percent_watched=avg,
                videos_watched=channel_n[cid],
            )
        )
    for cid, avg in category_avg.items():
        session.merge(
            CategoryInterest(category_id=cid, avg_percent_watched=avg, videos_watched=category_n[cid])
        )
    session.flush()

    return InterestProfile(
        global_avg_percent=global_avg,
        channel_avg_percent=channel_avg,
        channel_watch_count=channel_n,
        category_avg_percent=category_avg,
        category_watch_count=category_n,
    )


@dataclass
class PredictionResult:
    percent: float
    interesting: bool
    confidence: float
    model_version: str


class WatchPredictor:
    def __init__(self):
        self.model: GradientBoostingRegressor | None = None
        self.trained_at: datetime | None = None
        self.n_samples: int = 0

    # -- persistence ---------------------------------------------------
    def load(self) -> bool:
        path = model_path()
        if not path.exists():
            return False
        try:
            payload = joblib.load(path)
        except Exception:
            return False
        self.model = payload.get("model")
        self.trained_at = payload.get("trained_at")
        self.n_samples = payload.get("n_samples", 0)
        return self.model is not None

    def save(self) -> None:
        joblib.dump(
            {"model": self.model, "trained_at": self.trained_at, "n_samples": self.n_samples},
            model_path(),
        )

    # -- training --------------------------------------------------------
    def train(self, session: Session, min_samples: int = 15) -> int:
        """(Re)fit the model on all recorded watch events. Returns sample count.

        Uses leave-one-out channel/category averages per training row so the
        model can't trivially "cheat" by reading its own target out of the
        aggregate features.
        """
        events = (
            session.query(WatchEvent, Video)
            .join(Video, Video.video_id == WatchEvent.video_id)
            .all()
        )
        if len(events) < min_samples:
            self.model = None
            self.n_samples = len(events)
            return len(events)

        global_avg = sum(e.percent_watched for e, _ in events) / len(events)

        channel_sum: dict[str, float] = {}
        channel_n: dict[str, int] = {}
        category_sum: dict[str, float] = {}
        category_n: dict[str, int] = {}
        for e, v in events:
            if v.channel_id:
                channel_sum[v.channel_id] = channel_sum.get(v.channel_id, 0.0) + e.percent_watched
                channel_n[v.channel_id] = channel_n.get(v.channel_id, 0) + 1
            if v.category_id:
                category_sum[v.category_id] = category_sum.get(v.category_id, 0.0) + e.percent_watched
                category_n[v.category_id] = category_n.get(v.category_id, 0) + 1

        X = []
        y = []
        for e, v in events:
            sent_avg, sent_pos, sent_neg = _video_sentiment(session, v.video_id)

            if v.channel_id and channel_n.get(v.channel_id, 0) > 1:
                ch_avg = (channel_sum[v.channel_id] - e.percent_watched) / (channel_n[v.channel_id] - 1)
                ch_n = channel_n[v.channel_id] - 1
            else:
                ch_avg, ch_n = global_avg, 0

            if v.category_id and category_n.get(v.category_id, 0) > 1:
                cat_avg = (category_sum[v.category_id] - e.percent_watched) / (category_n[v.category_id] - 1)
                cat_n = category_n[v.category_id] - 1
            else:
                cat_avg, cat_n = global_avg, 0

            profile = InterestProfile(
                global_avg_percent=global_avg,
                channel_avg_percent={v.channel_id: ch_avg} if v.channel_id else {},
                channel_watch_count={v.channel_id: ch_n} if v.channel_id else {},
                category_avg_percent={v.category_id: cat_avg} if v.category_id else {},
                category_watch_count={v.category_id: cat_n} if v.category_id else {},
            )
            row = build_feature_row(
                duration_seconds=e.duration_seconds or v.duration_seconds,
                view_count=v.view_count,
                like_count=v.like_count,
                comment_count=v.comment_count,
                published_at=v.published_at,
                title=v.title,
                channel_id=v.channel_id,
                category_id=v.category_id,
                sentiment_avg=sent_avg,
                sentiment_positive_ratio=sent_pos,
                sentiment_negative_ratio=sent_neg,
                profile=profile,
                now=e.watched_at or datetime.now(timezone.utc),
            )
            X.append(row_to_vector(row))
            y.append(max(0.0, min(100.0, e.percent_watched)))

        model = GradientBoostingRegressor(
            n_estimators=150,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            random_state=42,
        )
        model.fit(np.array(X), np.array(y))

        self.model = model
        self.trained_at = datetime.now(timezone.utc)
        self.n_samples = len(events)
        self.save()
        return len(events)

    # -- prediction --------------------------------------------------------
    def predict(
        self,
        session: Session,
        video: Video,
        profile: InterestProfile,
        threshold: float = 60.0,
    ) -> PredictionResult:
        sent_avg, sent_pos, sent_neg = _video_sentiment(session, video.video_id)
        _, ch_n = profile.for_channel(video.channel_id)
        _, cat_n = profile.for_category(video.category_id)

        if self.model is not None:
            row = build_feature_row(
                duration_seconds=video.duration_seconds,
                view_count=video.view_count,
                like_count=video.like_count,
                comment_count=video.comment_count,
                published_at=video.published_at,
                title=video.title,
                channel_id=video.channel_id,
                category_id=video.category_id,
                sentiment_avg=sent_avg,
                sentiment_positive_ratio=sent_pos,
                sentiment_negative_ratio=sent_neg,
                profile=profile,
            )
            vector = np.array([row_to_vector(row)])
            percent = float(self.model.predict(vector)[0])
            percent = max(0.0, min(100.0, percent))
            confidence = max(0.3, min(1.0, 0.3 + 0.7 * min(1.0, (ch_n + cat_n) / 10.0)))
            version = MODEL_VERSION
        else:
            percent, confidence = self._heuristic(video, profile)
            version = "heuristic"

        return PredictionResult(
            percent=round(percent, 1),
            interesting=percent >= threshold,
            confidence=round(confidence, 2),
            model_version=version,
        )

    @staticmethod
    def _heuristic(video: Video, profile: InterestProfile) -> tuple[float, float]:
        ch_avg, ch_n = profile.for_channel(video.channel_id)
        cat_avg, cat_n = profile.for_category(video.category_id)
        if ch_n > 0 and cat_n > 0:
            percent = 0.7 * ch_avg + 0.3 * cat_avg
            confidence = 0.5
        elif ch_n > 0:
            percent = ch_avg
            confidence = 0.4
        elif cat_n > 0:
            percent = cat_avg
            confidence = 0.3
        else:
            percent = profile.global_avg_percent
            confidence = 0.2
        return max(0.0, min(100.0, percent)), confidence
