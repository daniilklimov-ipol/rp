import random
from datetime import datetime, timedelta, timezone

from ytpredictor.db import Video, WatchEvent, init_db, session_scope
from ytpredictor.model import WatchPredictor, recompute_interest_profile


def _seed(session, n=40, seed=1):
    rng = random.Random(seed)
    for i in range(n):
        liked_channel = i % 3 == 0
        session.add(
            Video(
                video_id=f"v{i}",
                title=f"Video {i}",
                channel_id="chA" if liked_channel else "chB",
                channel_title="A" if liked_channel else "B",
                duration_seconds=600,
                published_at=datetime.now(timezone.utc) - timedelta(days=10),
                category_id="27" if liked_channel else "20",
                view_count=10000,
                like_count=500,
                comment_count=50,
            )
        )
        percent = rng.uniform(70, 95) if liked_channel else rng.uniform(5, 30)
        session.add(
            WatchEvent(
                video_id=f"v{i}",
                watched_seconds=600 * percent / 100,
                duration_seconds=600,
                percent_watched=percent,
            )
        )
    session.flush()


def test_falls_back_to_heuristic_below_min_samples(isolated_appdata):
    init_db(f"sqlite:///{isolated_appdata}/test.db")
    with session_scope() as session:
        _seed(session, n=5)

    with session_scope() as session:
        predictor = WatchPredictor()
        n = predictor.train(session, min_samples=15)
        assert n == 5
        assert predictor.model is None


def test_trains_and_predicts_direction(isolated_appdata):
    init_db(f"sqlite:///{isolated_appdata}/test.db")
    with session_scope() as session:
        _seed(session, n=40)

    with session_scope() as session:
        predictor = WatchPredictor()
        n = predictor.train(session, min_samples=15)
        assert n == 40
        assert predictor.model is not None

        profile = recompute_interest_profile(session)

        liked_video = Video(
            video_id="new-liked",
            title="New liked-channel video",
            channel_id="chA",
            channel_title="A",
            duration_seconds=600,
            published_at=datetime.now(timezone.utc),
            category_id="27",
            view_count=5000,
            like_count=200,
            comment_count=20,
        )
        disliked_video = Video(
            video_id="new-disliked",
            title="New other-channel video",
            channel_id="chB",
            channel_title="B",
            duration_seconds=600,
            published_at=datetime.now(timezone.utc),
            category_id="20",
            view_count=5000,
            like_count=200,
            comment_count=20,
        )

        liked_result = predictor.predict(session, liked_video, profile)
        disliked_result = predictor.predict(session, disliked_video, profile)

        assert liked_result.percent > disliked_result.percent
        assert liked_result.interesting is True
        assert disliked_result.interesting is False


def test_model_persists_and_reloads(isolated_appdata):
    init_db(f"sqlite:///{isolated_appdata}/test.db")
    with session_scope() as session:
        _seed(session, n=20)

    with session_scope() as session:
        predictor = WatchPredictor()
        predictor.train(session, min_samples=15)

    reloaded = WatchPredictor()
    assert reloaded.load() is True
    assert reloaded.model is not None
    assert reloaded.n_samples == 20
