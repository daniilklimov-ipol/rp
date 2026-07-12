"""SQLAlchemy models and session management for the local SQLite database.

Tables:
    videos          - metadata + statistics pulled from the YouTube Data API
    comments        - top comments for a video, with a sentiment score each
    watch_events    - the user's actual watch history (real completion %)
    predictions     - cached model predictions per video
    channel_stats   - rolling per-channel completion stats (derived)
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from .paths import db_path

Base = declarative_base()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Video(Base):
    __tablename__ = "videos"

    video_id = Column(String(32), primary_key=True)
    title = Column(String(512), nullable=False, default="")
    channel_id = Column(String(64), index=True)
    channel_title = Column(String(256), default="")
    duration_seconds = Column(Integer, default=0)
    published_at = Column(DateTime, nullable=True)
    category_id = Column(String(16), default="")
    tags = Column(Text, default="")  # JSON-encoded list

    view_count = Column(Integer, default=0)
    like_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)

    fetched_at = Column(DateTime, default=utcnow)

    comments = relationship("Comment", back_populates="video", cascade="all, delete-orphan")
    watch_events = relationship("WatchEvent", back_populates="video", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="video", cascade="all, delete-orphan")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(32), ForeignKey("videos.video_id"), index=True)
    text = Column(Text, default="")
    like_count = Column(Integer, default=0)
    sentiment = Column(Float, default=0.0)  # VADER compound score, -1..1

    video = relationship("Video", back_populates="comments")


class WatchEvent(Base):
    """One real, observed watch session for a video (reported by the extension)."""

    __tablename__ = "watch_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(32), ForeignKey("videos.video_id"), index=True)
    watched_seconds = Column(Float, default=0.0)  # furthest playback position reached
    duration_seconds = Column(Float, default=0.0)  # video duration at watch time
    percent_watched = Column(Float, default=0.0)  # 0..100, clamped
    watched_at = Column(DateTime, default=utcnow)

    video = relationship("Video", back_populates="watch_events")

    @property
    def is_liked_pattern(self) -> bool:
        """Heuristic 'seemed interesting' flag used as a training label fallback."""
        return self.percent_watched >= 60.0


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(32), ForeignKey("videos.video_id"), index=True)
    predicted_percent = Column(Float, default=0.0)
    interesting = Column(Boolean, default=False)
    confidence = Column(Float, default=0.0)
    model_version = Column(String(32), default="heuristic")
    created_at = Column(DateTime, default=utcnow)

    video = relationship("Video", back_populates="predictions")


class ChannelInterest(Base):
    """Rolling aggregate of how much of a given channel's videos the user watches."""

    __tablename__ = "channel_interest"

    channel_id = Column(String(64), primary_key=True)
    channel_title = Column(String(256), default="")
    avg_percent_watched = Column(Float, default=0.0)
    videos_watched = Column(Integer, default=0)


class CategoryInterest(Base):
    """Rolling aggregate of how much of a given YouTube category the user watches."""

    __tablename__ = "category_interest"

    category_id = Column(String(16), primary_key=True)
    avg_percent_watched = Column(Float, default=0.0)
    videos_watched = Column(Integer, default=0)


_engine = None
_SessionLocal = None


def init_db(db_url: str | None = None):
    """Create the engine + tables. Call once at startup."""
    global _engine, _SessionLocal
    if db_url is None:
        db_url = f"sqlite:///{db_path()}"
    _engine = create_engine(db_url, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {})
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_session():
    if _SessionLocal is None:
        init_db()
    return _SessionLocal()


@contextmanager
def session_scope():
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
