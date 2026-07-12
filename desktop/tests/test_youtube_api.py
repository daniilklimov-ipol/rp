from ytpredictor.youtube_api import parse_iso8601_duration


def test_minutes_seconds():
    assert parse_iso8601_duration("PT4M13S") == 253


def test_hours_minutes_seconds():
    assert parse_iso8601_duration("PT1H2M3S") == 3723


def test_seconds_only():
    assert parse_iso8601_duration("PT45S") == 45


def test_hours_only():
    assert parse_iso8601_duration("PT2H") == 7200


def test_days():
    assert parse_iso8601_duration("P1DT2H") == 86400 + 7200


def test_empty_or_invalid():
    assert parse_iso8601_duration("") == 0
    assert parse_iso8601_duration("not-a-duration") == 0
