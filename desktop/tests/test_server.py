from fastapi.testclient import TestClient

from ytpredictor.config import Settings
from ytpredictor.server import create_app


def _client(isolated_appdata, **settings_overrides):
    settings = Settings(youtube_api_key="", server_port=8765, min_training_samples=3, **settings_overrides)
    app = create_app(settings)
    return TestClient(app)


def test_health(isolated_appdata):
    client = _client(isolated_appdata)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["model_trained"] is False
    assert body["api_key_configured"] is False


def test_watch_report_records_event_and_creates_video(isolated_appdata):
    client = _client(isolated_appdata)
    resp = client.post(
        "/watch",
        json={
            "video_id": "abc123",
            "watched_seconds": 80,
            "duration_seconds": 100,
            "title": "Test video",
            "channel_id": "ch1",
            "channel_title": "Chan One",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["percent_watched"] == 80.0

    history = client.get("/history").json()
    assert len(history) == 1
    assert history[0]["video_id"] == "abc123"
    assert history[0]["percent_watched"] == 80.0

    videos = client.get("/videos").json()
    assert videos[0]["video_id"] == "abc123"


def test_watch_report_rejects_zero_duration(isolated_appdata):
    client = _client(isolated_appdata)
    resp = client.post(
        "/watch",
        json={"video_id": "abc123", "watched_seconds": 10, "duration_seconds": 0},
    )
    assert resp.status_code == 400


def test_predict_without_api_key_falls_back_gracefully(isolated_appdata):
    client = _client(isolated_appdata)
    client.post(
        "/watch",
        json={
            "video_id": "abc123",
            "watched_seconds": 80,
            "duration_seconds": 100,
            "title": "Test video",
            "channel_id": "ch1",
            "channel_title": "Chan One",
        },
    )

    resp = client.post("/predict", json={"video_ids": ["abc123", "never-seen-before"]})
    assert resp.status_code == 200
    body = resp.json()
    predictions = {p["video_id"]: p for p in body["predictions"]}

    assert predictions["abc123"]["error"] is None
    assert 0 <= predictions["abc123"]["percent"] <= 100

    assert predictions["never-seen-before"]["error"] == "no_api_key"


def test_train_endpoint_reports_sample_count(isolated_appdata):
    client = _client(isolated_appdata)
    for i in range(3):
        client.post(
            "/watch",
            json={"video_id": f"v{i}", "watched_seconds": 50, "duration_seconds": 100},
        )
    resp = client.post("/train")
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_samples"] == 3
    assert body["model_trained"] is True  # min_training_samples=3 in this test client


def test_profile_endpoint(isolated_appdata):
    client = _client(isolated_appdata)
    client.post(
        "/watch",
        json={
            "video_id": "abc123",
            "watched_seconds": 90,
            "duration_seconds": 100,
            "channel_id": "ch1",
            "channel_title": "Chan One",
        },
    )
    resp = client.get("/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["channels"][0]["channel_id"] == "ch1"
    assert body["channels"][0]["avg_percent"] == 90.0
