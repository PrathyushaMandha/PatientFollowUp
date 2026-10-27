import pytest

from app.services.phq9 import ANSWER_OPTIONS, QUESTIONS, get_question, score_assessment


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "minimal"),
        (5, "mild"),
        (10, "moderate"),
        (15, "moderately severe"),
        (20, "severe"),
        (27, "severe"),
    ],
)
def test_score_boundaries(score: int, expected: str) -> None:
    scores = [0] * 9
    remaining = score
    for index in range(9):
        scores[index] = min(3, remaining)
        remaining -= scores[index]
    assert score_assessment(scores) == (score, expected)


def test_instrument_has_approved_shape() -> None:
    assert len(QUESTIONS) == 9
    assert len(ANSWER_OPTIONS) == 4
    assert "hurting yourself" in get_question(9).text


def test_rejects_incomplete_assessment() -> None:
    with pytest.raises(ValueError):
        score_assessment([0] * 8)
