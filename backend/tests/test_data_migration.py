import pytest

from scripts.migrate_sqlserver_to_postgresql import (
    prepare_user_rows,
    validate_dialects,
)


def test_prepare_user_rows_defers_patient_foreign_keys() -> None:
    original_rows = [
        {"id": 1, "username": "clinician", "patient_id": None},
        {"id": 2, "username": "patient", "patient_id": 7},
    ]

    prepared_rows, patient_links = prepare_user_rows(original_rows)

    assert prepared_rows[1]["patient_id"] is None
    assert patient_links == {2: 7}
    assert original_rows[1]["patient_id"] == 7


def test_validate_dialects_accepts_sqlserver_to_postgresql() -> None:
    validate_dialects("mssql", "postgresql")


@pytest.mark.parametrize(
    ("source", "target", "message"),
    [
        ("sqlite", "postgresql", "Source database"),
        ("mssql", "sqlite", "Target database"),
    ],
)
def test_validate_dialects_rejects_wrong_database_types(
    source: str, target: str, message: str
) -> None:
    with pytest.raises(RuntimeError, match=message):
        validate_dialects(source, target)
