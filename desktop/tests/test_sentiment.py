from ytpredictor.sentiment import score_text, summarize


def test_positive_text_scores_positive():
    assert score_text("This video is amazing, I loved it so much!") > 0.3


def test_negative_text_scores_negative():
    assert score_text("This was terrible and boring, total waste of time.") < -0.3


def test_empty_text_is_neutral():
    assert score_text("") == 0.0
    assert score_text("   ") == 0.0


def test_summarize_ratios():
    summary = summarize([0.8, 0.6, -0.7, 0.0])
    assert summary.count == 4
    assert summary.positive_ratio == 0.5
    assert summary.negative_ratio == 0.25


def test_summarize_empty():
    summary = summarize([])
    assert summary.count == 0
    assert summary.average == 0.0
