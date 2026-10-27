from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth import decode_access_token
from app.database import get_db
from app.models import Consultation, Patient, User


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
Database = Annotated[Session, Depends(get_db)]


def get_current_user(
    database: Database, token: Annotated[str, Depends(oauth2_scheme)]
) -> User:
    try:
        user_id = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = database.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive or unknown user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_clinician(user: CurrentUser) -> User:
    if user.role not in {"admin", "clinician"}:
        raise HTTPException(status_code=403, detail="Clinician access required")
    return user


Clinician = Annotated[User, Depends(require_clinician)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


Admin = Annotated[User, Depends(require_admin)]


def assert_patient_access(user: User, patient: Patient) -> None:
    owns_record = user.role == "clinician" and patient.created_by_user_id == user.id
    is_patient = user.role == "patient" and user.patient_id == patient.id
    if user.role != "admin" and not owns_record and not is_patient:
        raise HTTPException(status_code=403, detail="Patient record access denied")


def assert_consultation_access(user: User, consultation: Consultation) -> None:
    if user.role == "admin":
        return
    if user.role == "clinician" and consultation.clinician_user_id == user.id:
        return
    if user.role == "patient" and user.patient_id == consultation.patient_id:
        return
    raise HTTPException(status_code=403, detail="Consultation access denied")
