import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.dependencies import Clinician, CurrentUser, Database, assert_consultation_access, assert_patient_access
from app.config import get_settings
from app.models import Assessment, Consultation, ConsultationSummary, Message, Patient, SafetyEvent, VoiceRecording
from app.schemas import ConsultationView, MessageCreate, MessageView, SummaryReview, SummaryView, VoiceRecordingView
from app.services.agent import AgentUnavailableError, get_followup_agent
from app.services.audit import record_audit
from app.services.history import build_patient_memory
from app.services.phq9 import SAFETY_MESSAGE
from app.services.report import build_consultation_report, build_report_filename


router = APIRouter(tags=["consultations"])
SUMMARY_GENERATOR_VERSION = "groq_detailed_v1"
CONCERNING_PATTERN = re.compile(
    r"\b(kill myself|suicide|suicidal|hurt myself|self[- ]harm|better off dead)\b",
    re.IGNORECASE,
)
VOICE_CONTENT_TYPES = {
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
    "audio/webm": ".webm",
}


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


def _generate_consultation_summary(consultation: Consultation) -> str:
    conversation = [
        (message.role, message.content)
        for message in sorted(
            consultation.messages, key=lambda item: item.sequence_number
        )
    ]
    return get_followup_agent().extract_report_findings(conversation).summary


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
            "Content-Disposition": f'attachment; filename="{build_report_filename(patient, consultation)}"'
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
    "/consultations/{consultation_public_id}/voice-recordings",
    response_model=VoiceRecordingView,
    status_code=201,
)
def upload_voice_recording(
    consultation_public_id: str,
    database: Database,
    user: CurrentUser,
    recording: UploadFile = File(...),
) -> VoiceRecording:
    consultation = _get_consultation(database, consultation_public_id)
    assert_consultation_access(user, consultation)
    if user.role != "patient":
        raise HTTPException(status_code=403, detail="Patient access required")
    content_type = (recording.content_type or "").split(";", 1)[0].lower()
    extension = VOICE_CONTENT_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(status_code=415, detail="Unsupported audio format")

    settings = get_settings()
    recording_dir = Path(settings.voice_recording_dir)
    recording_dir.mkdir(parents=True, exist_ok=True)
    storage_key = f"{uuid.uuid4()}{extension}"
    destination = recording_dir / storage_key
    temporary = destination.with_suffix(f"{destination.suffix}.tmp")
    byte_size = 0
    try:
        with temporary.open("wb") as output:
            while chunk := recording.file.read(1024 * 1024):
                byte_size += len(chunk)
                if byte_size > settings.voice_recording_max_bytes:
                    raise HTTPException(status_code=413, detail="Voice recording is too large")
                output.write(chunk)
        if byte_size == 0:
            raise HTTPException(status_code=400, detail="Voice recording is empty")
        temporary.replace(destination)
        saved_recording = VoiceRecording(
            consultation_id=consultation.id,
            recorded_by_user_id=user.id,
            storage_key=storage_key,
            content_type=content_type,
            byte_size=byte_size,
        )
        database.add(saved_recording)
        database.flush()
        record_audit(database, user, "record_voice", "consultation", consultation.public_id)
        database.commit()
        database.refresh(saved_recording)
        return saved_recording
    except Exception:
        temporary.unlink(missing_ok=True)
        if destination.exists() and database.new:
            destination.unlink(missing_ok=True)
        database.rollback()
        raise


@router.get(
    "/consultations/{consultation_public_id}/voice-recordings",
    response_model=list[VoiceRecordingView],
)
def list_voice_recordings(
    consultation_public_id: str,
    database: Database,
    user: CurrentUser,
) -> list[VoiceRecording]:
    consultation = _get_consultation(database, consultation_public_id)
    assert_consultation_access(user, consultation)
    return list(database.scalars(
        select(VoiceRecording)
        .where(VoiceRecording.consultation_id == consultation.id)
        .order_by(VoiceRecording.created_at.desc(), VoiceRecording.id.desc())
    ))


@router.get("/voice-recordings/{recording_public_id}")
def download_voice_recording(
    recording_public_id: str,
    database: Database,
    user: CurrentUser,
) -> FileResponse:
    recording = database.scalar(
        select(VoiceRecording).where(VoiceRecording.public_id == recording_public_id)
    )
    if recording is None:
        raise HTTPException(status_code=404, detail="Voice recording not found")
    consultation = database.get(Consultation, recording.consultation_id)
    if consultation is None:
        raise HTTPException(status_code=404, detail="Consultation not found")
    assert_consultation_access(user, consultation)
    path = Path(get_settings().voice_recording_dir) / recording.storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Voice recording file not found")
    return FileResponse(path, media_type=recording.content_type, filename=recording.storage_key)


@router.post(
    "/consultations/{consultation_public_id}/complete", response_model=SummaryView
)
def complete_consultation(
    consultation_public_id: str, database: Database, user: CurrentUser
) -> ConsultationSummary:
    consultation = _get_consultation(database, consultation_public_id)
    assert_consultation_access(user, consultation)
    existing_summary = database.scalar(
        select(ConsultationSummary).where(
            ConsultationSummary.consultation_id == consultation.id
        )
    )
    if existing_summary is not None:
        return existing_summary
    if consultation.status != "active":
        raise HTTPException(status_code=409, detail="Consultation is already closed")
    messages = sorted(consultation.messages, key=lambda message: message.sequence_number)
    try:
        summary_content = _generate_consultation_summary(consultation)
    except AgentUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    summary = ConsultationSummary(
        consultation_id=consultation.id,
        content=summary_content,
        source_first_message_id=messages[0].id if messages else None,
        source_last_message_id=messages[-1].id if messages else None,
        generated_by=SUMMARY_GENERATOR_VERSION,
    )
    consultation.status = "completed"
    consultation.ended_at = datetime.utcnow()
    database.add(summary)
    record_audit(database, user, "complete", "consultation", consultation.public_id)
    try:
        database.commit()
    except IntegrityError:
        database.rollback()
        existing_summary = database.scalar(
            select(ConsultationSummary).where(
                ConsultationSummary.consultation_id == consultation.id
            )
        )
        if existing_summary is not None:
            return existing_summary
        raise
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
    if summary.generated_by != SUMMARY_GENERATOR_VERSION:
        try:
            summary.content = _generate_consultation_summary(consultation)
        except AgentUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        summary.generated_by = SUMMARY_GENERATOR_VERSION
        database.commit()
        database.refresh(summary)
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
