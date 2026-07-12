"""Comment sentiment scoring using VADER (lexicon-based, no network/model download)."""

from __future__ import annotations

from dataclasses import dataclass

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def score_text(text: str) -> float:
    """Return VADER's compound sentiment score in [-1, 1] for one comment."""
    if not text or not text.strip():
        return 0.0
    return _analyzer.polarity_scores(text)["compound"]


@dataclass
class SentimentSummary:
    average: float = 0.0
    positive_ratio: float = 0.0
    negative_ratio: float = 0.0
    count: int = 0


def summarize(scores: list[float]) -> SentimentSummary:
    if not scores:
        return SentimentSummary()
    n = len(scores)
    positives = sum(1 for s in scores if s >= 0.05)
    negatives = sum(1 for s in scores if s <= -0.05)
    return SentimentSummary(
        average=sum(scores) / n,
        positive_ratio=positives / n,
        negative_ratio=negatives / n,
        count=n,
    )
