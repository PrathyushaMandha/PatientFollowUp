from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentUser, Database, assert_consultation_access, assert_patient_access
from app.models import Assessment, AssessmentAnswer, Consultation, Patient, SafetyEvent
from app.schemas import (
    AnswerCreate,
    AnswerResult,
    AssessmentComparison,
    AssessmentStartResponse,
    AssessmentView,
    QuestionView,
)
from app.services.audit import record_audit
from app.services.history import latest_completed_assessment
from app.services.phq9 import ANSWER_OPTIONS, QUESTIONS, SAFETY_MESSAGE, get_question, score_assessment


router = APIRouter(tags=["assessments"])


def _get_assessment(database: Database, public_id: str) -> Assessment:
    assessment = database.scalar(
        select(Assessment)
        .options(selectinload(Assessment.answers))
        .where(Assessment.public_id == public_id)
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return assessment


def _question_view(number: int) -> QuestionView:
    question = get_question(number)
    return QuestionView(**question.__dict__)


@router.get("/phq9/questions", response_model=list[QuestionView])
def list_questions(user: CurrentUser) -> list[QuestionView]:
    return [_question_view(number) for number in range(1, 10)]


@router.post(
    "/consultations/{consultation_public_id}/assessments",
    response_model=AssessmentStartResponse,
    status_code=201,
)
def start_assessment(
    consultation_public_id: str, database: Database, user: CurrentUser
) -> AssessmentStartResponse:
    consultation = database.scalar(
        select(Consultation).where(Consultation.public_id == consultation_public_id)
    )
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    assert_consultation_access(user, consultation)
    if consultation.status != "active":
        raise HTTPException(status_code=409, detail="Consultation is not active")
    existing = database.scalar(
        select(Assessment).where(Assessment.consultation_id == consultation.id)
    )
    if existing:
        raise HTTPException(status_code=409, detail="This consultation already has an assessment")
    assessment = Assessment(
        consultation_id=consultation.id,
        patient_id=consultation.patient_id,
    )
    database.add(assessment)
    database.flush()
    record_audit(database, user, "start", "assessment", assessment.public_id)
    database.commit()
    return AssessmentStartResponse(
        public_id=assessment.public_id,
        status=assessment.status,
        next_question=_question_view(1),
    )


@router.post("/assessments/{assessment_public_id}/answers", response_model=AnswerResult)
def submit_answer(
    assessment_public_id: str,
    payload: AnswerCreate,
    database: Database,
    user: CurrentUser,
) -> AnswerResult:
    assessment = _get_assessment(database, assessment_public_id)
    consultation = database.get(Consultation, assessment.consultation_id)
    assert_consultation_access(user, consultation)
    if assessment.status != "in_progress":
        raise HTTPException(status_code=409, detail="Assessment is already complete")
    expected = len(assessment.answers) + 1
    if payload.question_number != expected:
        raise HTTPException(status_code=422, detail=f"Question {expected} must be answered next")
    answer = AssessmentAnswer(
        assessment_id=assessment.id,
        question_number=payload.question_number,
        question_text=QUESTIONS[payload.question_number - 1],
        score=payload.score,
        answer_text=ANSWER_OPTIONS[payload.score],
    )
    database.add(answer)
    assessment.answers.append(answer)
    safety_alert = payload.question_number == 9 and payload.score > 0
    if safety_alert:
        consultation.requires_review = True
        database.flush()
        database.add(
            SafetyEvent(
                consultation_id=consultation.id,
                assessment_answer_id=answer.id,
                reason=f"PHQ-9 question 9 response scored {payload.score}",
                action_taken=SAFETY_MESSAGE,
            )
        )
    next_question = None
    if payload.question_number == 9:
        ordered_scores = [item.score for item in sorted(
            assessment.answers, key=lambda item: item.question_number
        )]
        assessment.total_score, assessment.severity = score_assessment(ordered_scores)
        assessment.status = "completed"
        assessment.completed_at = datetime.utcnow()
    else:
        next_question = _question_view(payload.question_number + 1)
    record_audit(database, user, "answer", "assessment", assessment.public_id, str(payload.question_number))
    database.commit()
    assessment = _get_assessment(database, assessment.public_id)
    return AnswerResult(
        assessment=AssessmentView.model_validate(assessment),
        next_question=next_question,
        safety_alert=safety_alert,
        safety_message=SAFETY_MESSAGE if safety_alert else None,
    )


@router.get("/assessments/{assessment_public_id}", response_model=AssessmentView)
def get_assessment(
    assessment_public_id: str, database: Database, user: CurrentUser
) -> Assessment:
    assessment = _get_assessment(database, assessment_public_id)
    assert_consultation_access(user, database.get(Consultation, assessment.consultation_id))
    return assessment


@router.get(
    "/patients/{patient_public_id}/assessment-history",
    response_model=list[AssessmentComparison],
)
def assessment_history(
    patient_public_id: str, database: Database, user: CurrentUser
) -> list[AssessmentComparison]:
    patient = database.scalar(select(Patient).where(Patient.public_id == patient_public_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    assert_patient_access(user, patient)
    assessments = list(database.scalars(
        select(Assessment)
        .options(selectinload(Assessment.answers))
        .where(Assessment.patient_id == patient.id, Assessment.status == "completed")
        .order_by(Assessment.completed_at)
    ))
    comparisons: list[AssessmentComparison] = []
    previous: Assessment | None = None
    for assessment in assessments:
        previous_scores = {answer.question_number: answer.score for answer in previous.answers} if previous else {}
        current_scores = {answer.question_number: answer.score for answer in assessment.answers}
        comparisons.append(
            AssessmentComparison(
                assessment=AssessmentView.model_validate(assessment),
                score_change=(
                    assessment.total_score - previous.total_score
                    if previous and assessment.total_score is not None and previous.total_score is not None
                    else None
                ),
                answer_changes={
                    number: score - previous_scores[number]
                    for number, score in current_scores.items()
                    if number in previous_scores
                },
            )
        )
        previous = assessment
    return comparisons
