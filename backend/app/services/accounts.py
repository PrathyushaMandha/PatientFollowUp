import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


def normalize_patient_username(first_name: str) -> str:
    username = re.sub(r"[^a-z0-9]", "", first_name.lower())
    return username or "patient"


def available_patient_username(database: Session, first_name: str) -> str:
    base = normalize_patient_username(first_name)
    username = base
    suffix = 2
    while database.scalar(select(User.id).where(User.username == username)) is not None:
        username = f"{base}{suffix}"
        suffix += 1
    return username