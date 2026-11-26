from datetime import datetime
from io import BytesIO

from pypdf import PdfReader

from app.models import Assessment, Consultation, Message, Patient
from app.services.agent import ConversationFindings, SymptomFinding
from app.services.report import build_consultation_report, build_report_filename


def test_report_filename_uses_patient_name_and_consultation_date() -> None:
    patient = Patient(first_name="Ram", last_name="M / Test", created_by_user_id=1)
    consultation = Consultation(
        patient_id=1,
        clinician_user_id=1,
        started_at=datetime(2026, 10, 15, 9, 30),
    )

    assert build_report_filename(patient, consultation) == "Ram_M_Test_2026-10-15.pdf"


def test_builds_valid_report_when_assessment_exists() -> None:
    patient = Patient(
        id=1,
        public_id="patient-report-id",
        first_name="Test",
        last_name="Patient",
        created_by_user_id=1,
    )
    consultation = Consultation(
        id=1,
        public_id="consultation-report-id",
        patient_id=1,
        clinician_user_id=1,
        status="completed",
        started_at=datetime(2026, 1, 1),
        ended_at=datetime(2026, 1, 1),
    )
    assessment = Assessment(
        id=1,
        public_id="assessment-report-id",
        consultation_id=1,
        patient_id=1,
        status="completed",
        total_score=9,
        severity="mild",
        completed_at=datetime(2026, 1, 1),
    )
    assessment.answers = []

    report = build_consultation_report(patient, consultation, assessment, None)

    assert report.startswith(b"%PDF")
    assert len(report) > 2000
    report_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(report)).pages
    )
    assert "PHQ-9" not in report_text
    assert "Report focus" in report_text


def test_builds_conversation_report_without_assessment() -> None:
    patient = Patient(
        id=1,
        public_id="patient-report-id",
        first_name="Test",
        last_name="Patient",
        created_by_user_id=1,
    )
    consultation = Consultation(
        id=1,
        public_id="consultation-report-id",
        patient_id=1,
        clinician_user_id=1,
        status="completed",
        started_at=datetime(2026, 1, 1),
        ended_at=datetime(2026, 1, 1),
    )
    consultation.messages = [
        Message(
            role="patient",
            content="Private transcript wording must not appear in the report.",
            sequence_number=1,
        )
    ]

    findings = ConversationFindings(
        summary="The patient reported worsening knee pain.",
        symptoms=[
            SymptomFinding(
                symptom="Knee pain",
                change="Worsened",
                evidence="Private source statement must not appear in the report.",
            )
        ],
    )
    report = build_consultation_report(
        patient, consultation, None, None, findings
    )

    assert report.startswith(b"%PDF")
    assert len(report) > 2000
    report_text = "\n".join(
        page.extract_text() or "" for page in PdfReader(BytesIO(report)).pages
    )
    assert "Consultation overview" in report_text
    assert "Reported symptoms" in report_text
    assert "The patient reported worsening knee pain." in report_text
    assert "Knee pain" in report_text
    assert "Conversation record" not in report_text
    assert "Private transcript wording" not in report_text
    assert "Private source statement" not in report_text