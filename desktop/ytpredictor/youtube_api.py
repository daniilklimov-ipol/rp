"""Thin client around the YouTube Data API v3 (videos.list, commentThreads.list).

Only uses read-only, API-key-authenticated endpoints — no OAuth, no access to
a user's actual private watch history (YouTube does not expose that via the
public API). Real watch history is instead recorded locally by the browser
extension, see server.py's /watch endpoint.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import requests

API_BASE = "https://www.googleapis.com/youtube/v3"

_ISO8601_DURATION_RE = re.compile(
    r"P(?:(?P<days>\d+)D)?"
    r"T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?"
)


def parse_iso8601_duration(value: str) -> int:
    """Parse an ISO-8601 duration like 'PT4M13S' into whole seconds."""
    if not value:
        return 0
    match = _ISO8601_DURATION_RE.fullmatch(value.strip())
    if not match:
        return 0
    parts = match.groupdict(default="0")
    days = int(parts["days"])
    hours = int(parts["hours"])
    minutes = int(parts["minutes"])
    seconds = int(parts["seconds"])
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


@dataclass
class VideoMetadata:
    video_id: str
    title: str = ""
    channel_id: str = ""
    channel_title: str = ""
    duration_seconds: int = 0
    published_at: str | None = None
    category_id: str = ""
    tags: list[str] = field(default_factory=list)
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0


@dataclass
class CommentData:
    text: str
    like_count: int = 0


class YouTubeAPIError(RuntimeError):
    pass


class YouTubeClient:
    def __init__(self, api_key: str, session: requests.Session | None = None, timeout: float = 10.0):
        if not api_key:
            raise YouTubeAPIError("A YouTube Data API key is required.")
        self.api_key = api_key
        self.session = session or requests.Session()
        self.timeout = timeout

    def _get(self, path: str, params: dict) -> dict:
        params = {**params, "key": self.api_key}
        resp = self.session.get(f"{API_BASE}/{path}", params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise YouTubeAPIError(f"YouTube API error {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    def get_videos(self, video_ids: list[str]) -> list[VideoMetadata]:
        """Fetch snippet/contentDetails/statistics for up to 50 video IDs at a time."""
        results: list[VideoMetadata] = []
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i : i + 50]
            data = self._get(
                "videos",
                {"part": "snippet,contentDetails,statistics", "id": ",".join(chunk)},
            )
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                content = item.get("contentDetails", {})
                stats = item.get("statistics", {})
                results.append(
                    VideoMetadata(
                        video_id=item["id"],
                        title=snippet.get("title", ""),
                        channel_id=snippet.get("channelId", ""),
                        channel_title=snippet.get("channelTitle", ""),
                        duration_seconds=parse_iso8601_duration(content.get("duration", "")),
                        published_at=snippet.get("publishedAt"),
                        category_id=snippet.get("categoryId", ""),
                        tags=list(snippet.get("tags", [])),
                        view_count=int(stats.get("viewCount", 0) or 0),
                        like_count=int(stats.get("likeCount", 0) or 0),
                        comment_count=int(stats.get("commentCount", 0) or 0),
                    )
                )
        return results

    def get_top_comments(self, video_id: str, max_results: int = 20) -> list[CommentData]:
        """Fetch up to max_results top-level comments, ordered by relevance.

        Some videos have comments disabled; that's not fatal, just return [].
        """
        try:
            data = self._get(
                "commentThreads",
                {
                    "part": "snippet",
                    "videoId": video_id,
                    "order": "relevance",
                    "maxResults": min(max_results, 100),
                    "textFormat": "plainText",
                },
            )
        except YouTubeAPIError:
            return []
        out = []
        for item in data.get("items", []):
            top = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            out.append(
                CommentData(
                    text=top.get("textDisplay", ""),
                    like_count=int(top.get("likeCount", 0) or 0),
                )
            )
        return out
