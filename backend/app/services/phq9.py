from dataclasses import dataclass


INTRODUCTION = (
    "Over the last 2 weeks, how often have you been bothered by any of the "
    "following problems?"
)

QUESTIONS = (
    "Little interest or pleasure in doing things",
    "Feeling down, depressed, or hopeless",
    "Trouble falling or staying asleep, or sleeping too much",
    "Feeling tired or having little energy",
    "Poor appetite or overeating",
    "Feeling bad about yourself, or that you are a failure or have let yourself or your family down",
    "Trouble concentrating on things, such as reading the newspaper or watching television",
    "Moving or speaking so slowly that other people could have noticed, or the opposite, being so fidgety or restless that you have been moving around a lot more than usual",
    "Thoughts that you would be better off dead, or of hurting yourself in some way",
)

ANSWER_OPTIONS = (
    "Not at all",
    "Several days",
    "More than half the days",
    "Nearly every day",
)

SAFETY_MESSAGE = (
    "Your response indicates that immediate follow-up from a clinician is needed. "
    "If you may act on thoughts of self-harm or are in immediate danger, contact local "
    "emergency services now. In the U.S. or Canada, call or text 988. Do not rely on "
    "this application for emergency support."
)


@dataclass(frozen=True)
class Question:
    number: int
    text: str
    answer_options: list[str]


def get_question(number: int) -> Question:
    if number < 1 or number > len(QUESTIONS):
        raise ValueError("PHQ-9 question number must be between 1 and 9")
    return Question(number, QUESTIONS[number - 1], list(ANSWER_OPTIONS))


def score_assessment(scores: list[int]) -> tuple[int, str]:
    if len(scores) != 9 or any(score not in range(4) for score in scores):
        raise ValueError("PHQ-9 requires exactly nine answers scored from 0 to 3")
    total = sum(scores)
    if total <= 4:
        severity = "minimal"
    elif total <= 9:
        severity = "mild"
    elif total <= 14:
        severity = "moderate"
    elif total <= 19:
        severity = "moderately severe"
    else:
        severity = "severe"
    return total, severity
