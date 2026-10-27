import re
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.dependencies import Clinician, CurrentUser, Database, assert_consultation_access, assert_patient_access
from app.models import Assessment, Consultation, ConsultationSummary, Message, Patient, SafetyEvent
from app.schemas import ConsultationView, MessageCreate, MessageView, SummaryReview, SummaryView
from app.services.agent import AgentUnavailableError, get_followup_agent
from app.services.audit import record_audit
from app.services.history import build_patient_memory
from app.services.phq9 import SAFETY_MESSAGE
from app.services.report import build_consultation_report


router = APIRouter(tags=["consultations"])
CONCERNING_PATTERN = re.compile(
    r"\b(kill myself|suicide|suicidal|hurt myself|self[- ]harm|better off dead)\b",
    re.IGNORECASE,
)


def _get_consultation(database: Database, public_id: str) -> Consultation:
    consultation = database.scalar(
        select(Consultation)
        .options(
            selectinload(Consultation.messages),
            selectinload(Consultation.assessments),
        )
        .where(Consultation.public_id == public_id)
    )
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


@router.post(
    "/patients/{patient_public_id}/consultations",
    response_model=ConsultationView,
    status_code=201,
)
def start_consultation(
    patient_public_id: str, database: Database, user: CurrentUser
) -> Consultation:
    patient = database.scalar(select(Patient).where(Patient.public_id == patient_public_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    assert_patient_access(user, patient)
    existing = database.scalar(
        select(Consultation).where(
            Consultation.patient_id == patient.id, Consultation.status == "active"
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="Patient already has an active consultation")
    try:
        opening_text = get_followup_agent().opening_question(
            build_patient_memory(database, patient.id)
        )
    except AgentUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    clinician_user_id = (
        patient.created_by_user_id if user.role == "patient" else user.id
    )
    consultation = Consultation(
        patient_id=patient.id,
        clinician_user_id=clinician_user_id,
    )
    try:
        database.add(consultation)
        database.flush()
        opening = Message(
            consultation_id=consultation.id,
            chat_session_id=str(uuid.uuid4()),
            role="agent",
            content=opening_text,
            sequence_number=1,
        )
        database.add(opening)
        record_audit(database, user, "start", "consultation", consultation.public_id)
        database.commit()
    except IntegrityError:
        database.rollback()
        active_exists = database.scalar(
            select(Consultation.id).where(
                Consultation.patient_id == patient.id,
                Consultation.status == "active",
            )
        )
        if active_exists is not None:
            raise HTTPException(
                status_code=409,
                detail="Patient already has an active consultation",
            )
        raise
    return _get_consultation(database, consultation.public_id)


@router.get("/consultations/{consultation_public_id}", response_model=ConsultationView)
def get_consultation(
    consultation_public_id: str, database: Database, user: CurrentUser
) -> Consultation:
    consultation = _get_consultation(database, consultation_public_id)
    assert_consultation_access(user, consultation)
    return consultation


@router.get("/consultations/{consultation_public_id}/report.pdf")
def download_consultation_report(
    consultation_public_id: str, database: Database, user: CurrentUser
) -> Response:
    consultation = _get_consultation(database, consultation_public_id)
    assert_consultation_access(user, consultation)
    if consultation.status != "completed":
        raise HTTPException(status_code=409, detail="Report is available after consultation completion")
    assessment = database.scalar(
        select(Assessment)
        .options(selectinload(Assessment.answers))
        .where(
            Assessment.consultation_id == consultation.id,
            Assessment.status == "completed",
        )
        .order_by(Assessment.completed_at.desc())
    )
    patient = database.get(Patient, consultation.patient_id)
    summary = database.scalar(
        select(ConsultationSummary).where(
            ConsultationSummary.consultation_id == consultation.id
        )
    )
    conversation = [
        (message.role, message.content)
        for message in sorted(
            consultation.messages, key=lambda item: item.sequence_number
        )
    ]
    try:
        findings = get_followup_agent().extract_report_findings(conversation)
    except AgentUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    report = build_consultation_report(
        patient, consultation, assessment, summary, findings
    )
    record_audit(database, user, "download_report", "consultation", consultation.public_id)
    database.commit()
    return Response(
        content=report,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="patient-followup-report-{consultation.public_id[:8]}.pdf"'
            )
        },
    )


@router.get(
    "/patients/{patient_public_id}/consultations",
    response_model=list[ConsultationView],
)
def list_consultations(
    patient_public_id: str, database: Database, user: CurrentUser
) -> list[Consultation]:
    patient = database.scalar(select(Patient).where(Patient.public_id == patient_public_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    assert_patient_access(user, patient)
    return list(database.scalars(
        select(Consultation)
        .options(
            selectinload(Consultation.messages),
            selectinload(Consultation.assessments),
        )
        .where(Consultation.patient_id == patient.id)
        .order_by(Consultation.started_at.desc())
    ).unique())


@router.post(
    "/consultations/{consultation_public_id}/messages",
    response_model=list[MessageView],
    status_code=201,
)
def add_message(
    consultation_public_id: str,
    payload: MessageCreate,
    database: Database,
    user: CurrentUser,
) -> list[Message]:
    consultation = _get_consultation(database, consultation_public_id)
    assert_consultation_access(user, consultation)
    if consultation.status != "active":
        raise HTTPException(status_code=409, detail="Consultation is not active")
    next_sequence = (database.scalar(
        select(func.max(Message.sequence_number)).where(
            Message.consultation_id == consultation.id
        )
    ) or 0) + 1
    chat_session_id = consultation.messages[0].chat_session_id
    role = "patient" if user.role == "patient" else "clinician"
    incoming = Message(
        consultation_id=consultation.id,
        chat_session_id=chat_session_id,
        role=role,
        content=payload.content.strip(),
        sequence_number=next_sequence,
    )
    database.add(incoming)
    concerning = bool(CONCERNING_PATTERN.search(payload.content))
    if concerning:
        incoming.flagged = True
        consultation.requires_review = True
        response_text = SAFETY_MESSAGE
        database.add(
            SafetyEvent(
                consultation_id=consultation.id,
                reason="Concerning language detected in conversation",
                action_taken=SAFETY_MESSAGE,
            )
        )
    else:
        conversation_context = [
            (message.role, message.content)
            for message in sorted(
                consultation.messages, key=lambda item: item.sequence_number
            )
        ]
        try:
            response_text = get_followup_agent().followup_question(
                build_patient_memory(database, consultation.patient_id),
                conversation_context,
                payload.content,
            )
        except AgentUnavailableError as exc:
            database.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    outgoing = Message(
        consultation_id=consultation.id,
        chat_session_id=chat_session_id,
        role="agent",
        content=response_text,
        sequence_number=next_sequence + 1,
        flagged=concerning,
    )
    database.add(outgoing)
    record_audit(database, user, "message", "consultation", consultation.public_id)
    database.commit()
    database.refresh(incoming)
    database.refresh(outgoing)
    return [incoming, outgoing]


@router.post(
    "/consultations/{consultation_public_id}/complete", response_model=SummaryView
)
def complete_consultation(
    consultation_public_id: str, database: Database, user: CurrentUser
) -> ConsultationSummary:
    consultation = _get_consultation(database, consultation_public_id)
    assert_consultation_access(user, consultation)
    if consultation.status != "active":
        raise HTTPException(status_code=409, detail="Consultation is already closed")
    messages = sorted(consultation.messages, key=lambda message: message.sequence_number)
    excerpts = [
        f"{message.role.title()}: {message.content}"
        for message in messages
        if message.role in {"patient", "clinician"}
    ]
    summary = ConsultationSummary(
        consultation_id=consultation.id,
        content="\n".join(excerpts) or "No patient responses were recorded.",
        source_first_message_id=messages[0].id if messages else None,
        source_last_message_id=messages[-1].id if messages else None,
        generated_by="deterministic",
    )
    consultation.status = "completed"
    consultation.ended_at = datetime.utcnow()
    database.add(summary)
    record_audit(database, user, "complete", "consultation", consultation.public_id)
    database.commit()
    database.refresh(summary)
    return summary


@router.get(
    "/consultations/{consultation_public_id}/summary", response_model=SummaryView
)
def get_summary(
    consultation_public_id: str, database: Database, user: CurrentUser
) -> ConsultationSummary:
    consultation = _get_consultation(database, consultation_public_id)
    assert_consultation_access(user, consultation)
    summary = database.scalar(
        select(ConsultationSummary).where(
            ConsultationSummary.consultation_id == consultation.id
        )
    )
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    return summary


@router.patch("/summaries/{summary_id}", response_model=SummaryView)
def review_summary(
    summary_id: int,
    payload: SummaryReview,
    database: Database,
    clinician: Clinician,
) -> ConsultationSummary:
    summary = database.get(ConsultationSummary, summary_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="Summary not found")
    consultation = database.get(Consultation, summary.consultation_id)
    assert_consultation_access(clinician, consultation)
    summary.review_status = payload.review_status
    summary.reviewed_by_user_id = clinician.id
    summary.reviewed_at = datetime.utcnow()
    record_audit(database, clinician, "review", "summary", summary.id, payload.review_status)
    database.commit()
    database.refresh(summary)
    return summary
