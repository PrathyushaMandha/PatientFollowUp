import pytest
from pydantic import ValidationError

from app.schemas import PatientSignup, UserCreate


def test_staff_signup_accepts_clinician() -> None:
    user = UserCreate(username="clinician.two", password="StrongPass123!", role="clinician")
    assert user.role == "clinician"


def test_staff_signup_rejects_patient_role() -> None:
    with pytest.raises(ValidationError):
        UserCreate(username="patient-user", password="StrongPass123!", role="patient")


def test_staff_signup_rejects_short_password() -> None:
    with pytest.raises(ValidationError):
        UserCreate(username="new-admin", password="short", role="admin")


def test_patient_signup_has_no_role_field() -> None:
    signup = PatientSignup(
        first_name="New",
        last_name="Patient",
        username="new.patient",
        password="StrongPass123!",
    )
    assert not hasattr(signup, "role")