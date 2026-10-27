from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import Clinician, Database
from app.models import Consultation, SafetyEvent
from app.schemas import SafetyEventView, SafetyUpdate
from app.services.audit import record_audit


router = APIRouter(prefix="/safety-events", tags=["safety"])


@router.get("", response_model=list[SafetyEventView])
def list_safety_events(database: Database, clinician: Clinician) -> list[SafetyEvent]:
    statement = select(SafetyEvent).join(Consultation)
    if clinician.role != "admin":
        statement = statement.where(Consultation.clinician_user_id == clinician.id)
    return list(database.scalars(statement.order_by(SafetyEvent.created_at.desc())))


@router.patch("/{event_id}", response_model=SafetyEventView)
def update_safety_event(
    event_id: int,
    payload: SafetyUpdate,
    database: Database,
    clinician: Clinician,
) -> SafetyEvent:
    event = database.get(SafetyEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Safety event not found")
    consultation = database.get(Consultation, event.consultation_id)
    if clinician.role != "admin" and consultation.clinician_user_id != clinician.id:
        raise HTTPException(status_code=403, detail="Safety event access denied")
    event.status = payload.status
    event.acknowledged_by_user_id = clinician.id
    if payload.status == "resolved":
        event.resolved_at = datetime.utcnow()
    record_audit(database, clinician, payload.status, "safety_event", event.id)
    database.commit()
    database.refresh(event)
    return event
