from datetime import datetime, timedelta, timezone

from ytpredictor.features import FEATURE_NAMES, InterestProfile, build_feature_row, row_to_vector


def _base_kwargs(**overrides):
    kwargs = dict(
        duration_seconds=600,
        view_count=10000,
        like_count=500,
        comment_count=50,
        published_at=datetime.now(timezone.utc) - timedelta(days=5),
        title="Some video title",
        channel_id="chA",
        category_id="27",
        sentiment_avg=0.2,
        sentiment_positive_ratio=0.6,
        sentiment_negative_ratio=0.1,
        profile=InterestProfile(),
    )
    kwargs.update(overrides)
    return kwargs


def test_row_has_all_expected_features():
    row = build_feature_row(**_base_kwargs())
    assert set(row.keys()) == set(FEATURE_NAMES)


def test_row_to_vector_matches_order():
    row = build_feature_row(**_base_kwargs())
    vector = row_to_vector(row)
    assert vector == [row[name] for name in FEATURE_NAMES]


def test_is_short_flag():
    short = build_feature_row(**_base_kwargs(duration_seconds=30))
    long_video = build_feature_row(**_base_kwargs(duration_seconds=600))
    assert short["is_short"] == 1.0
    assert long_video["is_short"] == 0.0


def test_naive_datetime_does_not_crash():
    naive = datetime.now() - timedelta(days=2)
    row = build_feature_row(**_base_kwargs(published_at=naive))
    assert row["days_since_publish_log"] >= 0


def test_missing_published_at_uses_fallback():
    row = build_feature_row(**_base_kwargs(published_at=None))
    assert row["days_since_publish_log"] > 0


def test_interest_profile_defaults_to_global_average():
    profile = InterestProfile(global_avg_percent=42.0)
    avg, n = profile.for_channel("unknown-channel")
    assert avg == 42.0
    assert n == 0


def test_interest_profile_returns_known_channel_stats():
    profile = InterestProfile(
        global_avg_percent=50.0,
        channel_avg_percent={"chA": 88.0},
        channel_watch_count={"chA": 7},
    )
    avg, n = profile.for_channel("chA")
    assert avg == 88.0
    assert n == 7
