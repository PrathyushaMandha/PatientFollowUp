from sqlalchemy import select

from app.auth import hash_password
from app.config import get_settings
from app.database import SessionLocal
from app.models import Patient, User
from app.services.accounts import available_patient_username, normalize_patient_username


def main() -> None:
    settings = get_settings()
    with SessionLocal() as database:
        patients = list(database.scalars(select(Patient).order_by(Patient.id)))
        for patient in patients:
            user = database.scalar(
                select(User).where(User.patient_id == patient.id, User.role == "patient")
            )
            desired = normalize_patient_username(patient.first_name)
            owner = database.scalar(select(User).where(User.username == desired))
            username = (
                desired
                if owner is None or (user is not None and owner.id == user.id)
                else available_patient_username(database, patient.first_name)
            )
            if user is None:
                user = User(role="patient", patient_id=patient.id)
                database.add(user)
            user.username = username
            user.password_hash = hash_password(settings.patient_default_password)
            user.is_active = True
            print(f"Patient {patient.public_id}: {username}")
        database.commit()


if __name__ == "__main__":
    main()