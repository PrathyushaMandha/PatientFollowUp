from io import BytesIO
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.models import Assessment, Consultation, ConsultationSummary, Patient
from app.services.agent import ConversationFindings


def build_report_filename(patient: Patient, consultation: Consultation) -> str:
    patient_name = re.sub(
        r"[^A-Za-z0-9_-]+",
        "_",
        f"{patient.first_name}_{patient.last_name}".strip("_"),
    ).strip("_") or "patient"
    consultation_date = consultation.started_at.date().isoformat()
    return f"{patient_name}_{consultation_date}.pdf"


def build_consultation_report(
    patient: Patient,
    consultation: Consultation,
    assessment: Assessment | None,
    summary: ConsultationSummary | None,
    findings: ConversationFindings | None = None,
) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        title="Patient Follow-up Report",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        textColor=colors.white,
        fontSize=17,
        leading=21,
        alignment=TA_CENTER,
        spaceAfter=0,
    )
    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#173F3A"),
        fontSize=11,
        leading=14,
        spaceBefore=10,
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=styles["BodyText"],
        textColor=colors.HexColor("#59645F"),
        fontSize=8,
        leading=11,
    )

    story = [
        Table(
            [[Paragraph("PATIENT FOLLOW-UP REPORT", title_style)]],
            colWidths=[7.4 * inch],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#173F3A")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#0C2925")),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ]
            ),
        ),
        Spacer(1, 12),
        Paragraph("Patient and consultation", section_style),
    ]
    patient_name = f"{patient.first_name} {patient.last_name}".strip()
    details = [
        ["Patient", escape(patient_name), "Patient ID", patient.public_id],
        [
            "Date of birth",
            patient.date_of_birth.date().isoformat() if patient.date_of_birth else "Not recorded",
            "Consultation date",
            consultation.started_at.date().isoformat(),
        ],
        [
            "Completed",
            consultation.ended_at.date().isoformat() if consultation.ended_at else "Not recorded",
            "Report focus",
            "Reported symptoms",
        ],
    ]
    story.append(
        Table(
            details,
            colWidths=[1.05 * inch, 2.45 * inch, 1.15 * inch, 2.75 * inch],
            style=TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#59645F")),
                    ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#59645F")),
                    ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
                    ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F2F6F4")),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D4DDD9")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            ),
        )
    )

    findings = findings or ConversationFindings()
    story.extend(
        [
            Paragraph("Consultation overview", section_style),
            Paragraph(escape(findings.summary), small_style),
            Paragraph("Reported symptoms", section_style),
        ]
    )
    if findings.symptoms:
        finding_rows = [["Symptom", "Change", "Timeframe", "Daily impact"]]
        finding_rows.extend(
            [
                Paragraph(escape(item.symptom), cell_style),
                Paragraph(escape(item.change), cell_style),
                Paragraph(escape(item.timeframe), cell_style),
                Paragraph(escape(item.impact), cell_style),
            ]
            for item in findings.symptoms
        )
        story.append(
            Table(
                finding_rows,
                repeatRows=1,
                colWidths=[1.5 * inch, 1.2 * inch, 1.5 * inch, 2.8 * inch],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2A6159")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 7.5),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6F4")]),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#BCC9C4")),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                ),
            )
        )
    else:
        story.append(
            Paragraph("No symptoms were explicitly reported in the conversation.", small_style)
        )
    story.append(
        Paragraph(
            "AI-extracted symptom findings are drafts and require clinician review.",
            small_style,
        )
    )

    story.extend(
        [
            Paragraph("Consultation summary", section_style),
            Paragraph(
                escape(summary.content)
                if summary and summary.review_status == "approved"
                else "The consultation summary is pending clinician approval.",
                small_style,
            ),
            Spacer(1, 12),
            Paragraph(
                "This report supports clinician review and does not provide a diagnosis or treatment recommendation. Seek immediate local emergency support for urgent safety concerns.",
                small_style,
            ),
        ]
    )
    document.build(story)
    return buffer.getvalue()