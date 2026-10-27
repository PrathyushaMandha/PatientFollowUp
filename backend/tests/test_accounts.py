from app.services.accounts import normalize_patient_username


def test_patient_username_uses_normalized_first_name() -> None:
    assert normalize_patient_username("Prathyusha") == "prathyusha"
    assert normalize_patient_username("Mary Jane") == "maryjane"


def test_empty_patient_name_has_safe_fallback() -> None:
    assert normalize_patient_username("---") == "patient"