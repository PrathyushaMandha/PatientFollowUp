from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Assessment, Consultation, ConsultationSummary, Message
from app.services.phq9 import QUESTIONS


@dataclass
class PatientMemory:
    assessments: list[str] = field(default_factory=list)
    approved_summaries: list[str] = field(default_factory=list)
    patient_statements: list[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        sections = []
        if self.assessments:
            sections.append("Previous assessments:\n- " + "\n- ".join(self.assessments))
        if self.approved_summaries:
            sections.append("Clinician-approved summaries:\n- " + "\n- ".join(self.approved_summaries))
        if self.patient_statements:
            sections.append("Recent patient statements:\n- " + "\n- ".join(self.patient_statements))
        return "\n\n".join(sections) or "No previous consultation history is available."


def latest_completed_assessment(
    database: Session, patient_id: int, exclude_consultation_id: int | None = None
) -> Assessment | None:
    statement = (
        select(Assessment)
        .options(selectinload(Assessment.answers))
        .where(Assessment.patient_id == patient_id, Assessment.status == "completed")
        .order_by(Assessment.completed_at.desc())
    )
    if exclude_consultation_id is not None:
        statement = statement.where(Assessment.consultation_id != exclude_consultation_id)
    return database.scalars(statement).first()


def build_patient_memory(database: Session, patient_id: int) -> PatientMemory:
    memory = PatientMemory()
    assessments = list(database.scalars(
        select(Assessment)
        .options(selectinload(Assessment.answers))
        .where(Assessment.patient_id == patient_id, Assessment.status == "completed")
        .order_by(Assessment.completed_at.desc())
        .limit(3)
    ))
    for assessment in assessments:
        symptoms = [
            f"{QUESTIONS[answer.question_number - 1]}: {answer.answer_text}"
            for answer in sorted(assessment.answers, key=lambda item: item.question_number)
            if answer.score > 0
        ]
        completed = assessment.completed_at.date().isoformat() if assessment.completed_at else "unknown date"
        memory.assessments.append(
            f"{completed}, PHQ-9 score {assessment.total_score}/27 ({assessment.severity}); "
            + ("; ".join(symptoms) if symptoms else "no positively scored symptoms")
        )

    memory.approved_summaries = list(database.scalars(
        select(ConsultationSummary.content)
        .join(Consultation, Consultation.id == ConsultationSummary.consultation_id)
        .where(
            Consultation.patient_id == patient_id,
            ConsultationSummary.review_status == "approved",
        )
        .order_by(ConsultationSummary.reviewed_at.desc())
        .limit(3)
    ))
    statements = list(database.scalars(
        select(Message.content)
        .join(Consultation, Consultation.id == Message.consultation_id)
        .where(
            Consultation.patient_id == patient_id,
            Consultation.status == "completed",
            Message.role.in_(("patient", "clinician")),
        )
        .order_by(Message.created_at.desc())
        .limit(12)
    ))
    memory.patient_statements = list(reversed(statements))
    return memory
