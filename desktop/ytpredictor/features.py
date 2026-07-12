"""Feature engineering: turn a Video (+ the user's interest profile) into a
fixed-order numeric feature vector consumed by the ML model.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

FEATURE_NAMES = [
    "duration_minutes",
    "duration_log",
    "is_short",
    "views_log",
    "like_ratio",
    "comment_ratio",
    "sentiment_avg",
    "sentiment_positive_ratio",
    "sentiment_negative_ratio",
    "days_since_publish_log",
    "title_length",
    "channel_avg_percent",
    "channel_familiarity_log",
    "category_avg_percent",
    "category_familiarity_log",
]


@dataclass
class InterestProfile:
    """Rolling per-channel / per-category completion averages for one user."""

    global_avg_percent: float = 50.0
    channel_avg_percent: dict[str, float] | None = None
    channel_watch_count: dict[str, int] | None = None
    category_avg_percent: dict[str, float] | None = None
    category_watch_count: dict[str, int] | None = None

    def __post_init__(self):
        self.channel_avg_percent = self.channel_avg_percent or {}
        self.channel_watch_count = self.channel_watch_count or {}
        self.category_avg_percent = self.category_avg_percent or {}
        self.category_watch_count = self.category_watch_count or {}

    def for_channel(self, channel_id: str) -> tuple[float, int]:
        return (
            self.channel_avg_percent.get(channel_id, self.global_avg_percent),
            self.channel_watch_count.get(channel_id, 0),
        )

    def for_category(self, category_id: str) -> tuple[float, int]:
        return (
            self.category_avg_percent.get(category_id, self.global_avg_percent),
            self.category_watch_count.get(category_id, 0),
        )


def build_feature_row(
    *,
    duration_seconds: float,
    view_count: int,
    like_count: int,
    comment_count: int,
    published_at: datetime | None,
    title: str,
    channel_id: str,
    category_id: str,
    sentiment_avg: float,
    sentiment_positive_ratio: float,
    sentiment_negative_ratio: float,
    profile: InterestProfile,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    duration_seconds = max(float(duration_seconds), 0.0)
    view_count = max(int(view_count), 0)

    if published_at is not None:
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        days_since = max((now - published_at).total_seconds() / 86400.0, 0.0)
    else:
        days_since = 365.0  # unknown -> assume a stale, "typical" video

    channel_avg, channel_n = profile.for_channel(channel_id)
    category_avg, category_n = profile.for_category(category_id)

    return {
        "duration_minutes": duration_seconds / 60.0,
        "duration_log": math.log1p(duration_seconds),
        "is_short": 1.0 if duration_seconds > 0 and duration_seconds <= 60 else 0.0,
        "views_log": math.log1p(view_count),
        "like_ratio": (like_count / view_count) if view_count else 0.0,
        "comment_ratio": (comment_count / view_count) if view_count else 0.0,
        "sentiment_avg": sentiment_avg,
        "sentiment_positive_ratio": sentiment_positive_ratio,
        "sentiment_negative_ratio": sentiment_negative_ratio,
        "days_since_publish_log": math.log1p(days_since),
        "title_length": float(len(title or "")),
        "channel_avg_percent": channel_avg,
        "channel_familiarity_log": math.log1p(channel_n),
        "category_avg_percent": category_avg,
        "category_familiarity_log": math.log1p(category_n),
    }


def row_to_vector(row: dict) -> list[float]:
    return [float(row[name]) for name in FEATURE_NAMES]
