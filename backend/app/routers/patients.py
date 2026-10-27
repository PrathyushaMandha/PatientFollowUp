from datetime import datetime, time

from fastapi import APIRouter, HTTPException
from sqlalchemy import or_, select

from app.auth import hash_password
from app.config import get_settings
from app.dependencies import Clinician, CurrentUser, Database, assert_patient_access
from app.models import Patient, User
from app.schemas import PatientCreate, PatientView
from app.services.audit import record_audit
from app.services.accounts import available_patient_username


router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientView, status_code=201)
def create_patient(
    payload: PatientCreate, database: Database, clinician: Clinician
) -> Patient:
    if payload.portal_username and database.scalar(
        select(User).where(User.username == payload.portal_username)
    ):
        raise HTTPException(status_code=409, detail="Username already exists")
    patient = Patient(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        date_of_birth=(
            datetime.combine(payload.date_of_birth, time.min)
            if payload.date_of_birth
            else None
        ),
        created_by_user_id=clinician.id,
    )
    database.add(patient)
    database.flush()
    username = (
        payload.portal_username.strip()
        if payload.portal_username
        else available_patient_username(database, patient.first_name)
    )
    password = payload.portal_password or get_settings().patient_default_password
    database.add(
        User(
            username=username,
            password_hash=hash_password(password),
            role="patient",
            patient_id=patient.id,
        )
    )
    record_audit(database, clinician, "create", "patient", patient.public_id)
    database.commit()
    database.refresh(patient)
    return patient


@router.get("", response_model=list[PatientView])
def list_patients(database: Database, user: CurrentUser) -> list[Patient]:
    statement = select(Patient).where(Patient.is_active == True).order_by(  # noqa: E712
        Patient.last_name, Patient.first_name
    )
    if user.role == "clinician":
        statement = statement.where(Patient.created_by_user_id == user.id)
    elif user.role == "patient":
        statement = statement.where(Patient.id == user.patient_id)
    elif user.role != "admin":
        statement = statement.where(or_(False))
    return list(database.scalars(statement))


@router.get("/{patient_public_id}", response_model=PatientView)
def get_patient(
    patient_public_id: str, database: Database, user: CurrentUser
) -> Patient:
    patient = database.scalar(
        select(Patient).where(Patient.public_id == patient_public_id)
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    assert_patient_access(user, patient)
    record_audit(database, user, "read", "patient", patient.public_id)
    database.commit()
    return patient
