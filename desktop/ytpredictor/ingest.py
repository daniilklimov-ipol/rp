"""Fetch video metadata + comments from YouTube and persist/refresh them in the DB."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from . import sentiment
from .db import Comment, Video
from .youtube_api import YouTubeClient

REFRESH_AFTER = timedelta(hours=12)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def ensure_videos(session: Session, client: YouTubeClient, video_ids: list[str]) -> list[Video]:
    """Return Video rows for the given IDs, fetching/refreshing from the API as needed."""
    video_ids = list(dict.fromkeys(v for v in video_ids if v))
    if not video_ids:
        return []

    now = datetime.now(timezone.utc)
    existing = {v.video_id: v for v in session.query(Video).filter(Video.video_id.in_(video_ids)).all()}

    stale_or_missing = [
        vid
        for vid in video_ids
        if vid not in existing
        or existing[vid].fetched_at is None
        or (now - existing[vid].fetched_at.replace(tzinfo=timezone.utc)) > REFRESH_AFTER
    ]

    if stale_or_missing:
        metas = client.get_videos(stale_or_missing)
        for meta in metas:
            row = existing.get(meta.video_id) or Video(video_id=meta.video_id)
            row.title = meta.title
            row.channel_id = meta.channel_id
            row.channel_title = meta.channel_title
            row.duration_seconds = meta.duration_seconds
            row.published_at = _parse_dt(meta.published_at)
            row.category_id = meta.category_id
            row.tags = json.dumps(meta.tags)
            row.view_count = meta.view_count
            row.like_count = meta.like_count
            row.comment_count = meta.comment_count
            row.fetched_at = now
            session.merge(row)
            existing[meta.video_id] = row

            _refresh_comments(session, client, meta.video_id)

        session.flush()

    return [existing[vid] for vid in video_ids if vid in existing]


def _refresh_comments(session: Session, client: YouTubeClient, video_id: str, max_results: int = 20) -> None:
    session.query(Comment).filter(Comment.video_id == video_id).delete()
    for c in client.get_top_comments(video_id, max_results=max_results):
        session.add(
            Comment(
                video_id=video_id,
                text=c.text,
                like_count=c.like_count,
                sentiment=sentiment.score_text(c.text),
            )
        )
