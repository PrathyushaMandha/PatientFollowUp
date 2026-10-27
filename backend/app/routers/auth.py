from datetime import datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select

from app.auth import create_access_token, hash_password, verify_password
from app.config import get_settings
from app.dependencies import Admin, CurrentUser, Database
from app.models import Patient, User
from app.schemas import PatientSignup, Token, UserCreate, UserView
from app.services.audit import record_audit


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/bootstrap", response_model=Token, status_code=201)
def bootstrap_clinician(database: Database) -> Token:
    if database.scalar(select(func.count()).select_from(User)):
        raise HTTPException(status_code=409, detail="Bootstrap has already been completed")
    settings = get_settings()
    user = User(
        username=settings.bootstrap_username,
        password_hash=hash_password(settings.bootstrap_password),
        role="admin",
    )
    database.add(user)
    database.flush()
    record_audit(database, user, "bootstrap", "user", user.id)
    database.commit()
    return Token(access_token=create_access_token(user.id, user.role))


@router.post("/login", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()], database: Database
) -> Token:
    user = database.scalar(select(User).where(User.username == form.username))
    if user is None or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    record_audit(database, user, "login", "user", user.id)
    database.commit()
    return Token(access_token=create_access_token(user.id, user.role))


@router.post("/patient-signup", response_model=Token, status_code=201)
def patient_signup(payload: PatientSignup, database: Database) -> Token:
    username = payload.username.strip()
    if database.scalar(select(User.id).where(User.username == username)) is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    owner = database.scalar(
        select(User).where(User.role == "admin", User.is_active == True).order_by(User.id)  # noqa: E712
    )
    if owner is None:
        raise HTTPException(status_code=503, detail="Patient registration is unavailable")
    patient = Patient(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        date_of_birth=(
            datetime.combine(payload.date_of_birth, time.min)
            if payload.date_of_birth
            else None
        ),
        created_by_user_id=owner.id,
    )
    database.add(patient)
    database.flush()
    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        role="patient",
        patient_id=patient.id,
    )
    database.add(user)
    database.flush()
    record_audit(database, user, "self_signup", "patient", patient.public_id)
    database.commit()
    return Token(access_token=create_access_token(user.id, user.role))


@router.get("/me", response_model=UserView)
def me(user: CurrentUser) -> User:
    return user


@router.get("/users", response_model=list[UserView])
def list_users(database: Database, admin: Admin) -> list[User]:
    return list(database.scalars(select(User).order_by(User.username)))


@router.post("/signup", response_model=UserView, status_code=201)
def signup_user(
    payload: UserCreate, database: Database, admin: Admin
) -> User:
    username = payload.username.strip()
    if database.scalar(select(User.id).where(User.username == username)) is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    database.add(user)
    database.flush()
    record_audit(database, admin, "create", "user", user.id, payload.role)
    database.commit()
    database.refresh(user)
    return user
