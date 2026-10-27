import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.sysutcdatetime(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.sysutcdatetime(),
        onupdate=func.sysutcdatetime(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'clinician', 'patient')", name="ck_users_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="clinician")
    patient_id: Mapped[int | None] = mapped_column(
        ForeignKey("patients.id", use_alter=True, name="fk_users_patient_id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Patient(TimestampMixin, Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    consultations: Mapped[list["Consultation"]] = relationship(
        back_populates="patient", cascade="all, delete-orphan"
    )


class Consultation(TimestampMixin, Base):
    __tablename__ = "consultations"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'cancelled')", name="ck_consultations_status"),
        Index("ix_consultations_patient_started", "patient_id", "started_at"),
        Index(
            "uq_consultations_one_active_per_patient",
            "patient_id",
            unique=True,
            mssql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    clinician_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="active")
    started_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.sysutcdatetime()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)

    patient: Mapped[Patient] = relationship(back_populates="consultations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="consultation", cascade="all, delete-orphan"
    )
    assessments: Mapped[list["Assessment"]] = relationship(
        back_populates="consultation", cascade="all, delete-orphan"
    )

    @property
    def has_assessment(self) -> bool:
        return bool(self.assessments)


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint("role IN ('patient', 'agent', 'clinician', 'system')", name="ck_messages_role"),
        Index("ix_messages_consultation_created", "consultation_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"))
    chat_session_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sequence_number: Mapped[int] = mapped_column(Integer)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.sysutcdatetime()
    )

    consultation: Mapped[Consultation] = relationship(back_populates="messages")


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint("status IN ('in_progress', 'completed')", name="ck_assessments_status"),
        CheckConstraint("total_score IS NULL OR total_score BETWEEN 0 AND 27", name="ck_assessments_score"),
        Index("ix_assessments_patient_completed", "patient_id", "completed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"))
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    instrument: Mapped[str] = mapped_column(String(30), default="PHQ-9")
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    total_score: Mapped[int | None] = mapped_column(Integer)
    severity: Mapped[str | None] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.sysutcdatetime()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)

    consultation: Mapped[Consultation] = relationship(back_populates="assessments")
    answers: Mapped[list["AssessmentAnswer"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"
    __table_args__ = (
        UniqueConstraint("assessment_id", "question_number", name="uq_assessment_question"),
        CheckConstraint("question_number BETWEEN 1 AND 9", name="ck_answers_question"),
        CheckConstraint("score BETWEEN 0 AND 3", name="ck_answers_score"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessments.id"))
    question_number: Mapped[int] = mapped_column(Integer)
    question_text: Mapped[str] = mapped_column(String(500))
    score: Mapped[int] = mapped_column(Integer)
    answer_text: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.sysutcdatetime()
    )

    assessment: Mapped[Assessment] = relationship(back_populates="answers")


class ConsultationSummary(Base):
    __tablename__ = "consultation_summaries"
    __table_args__ = (
        CheckConstraint("review_status IN ('draft', 'approved', 'rejected')", name="ck_summaries_review"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"), unique=True)
    content: Mapped[str] = mapped_column(Text)
    source_first_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    source_last_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"))
    generated_by: Mapped[str] = mapped_column(String(50), default="deterministic")
    review_status: Mapped[str] = mapped_column(String(20), default="draft")
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.sysutcdatetime()
    )


class SafetyEvent(Base):
    __tablename__ = "safety_events"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'acknowledged', 'resolved')", name="ck_safety_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"))
    assessment_answer_id: Mapped[int | None] = mapped_column(ForeignKey("assessment_answers.id"))
    reason: Mapped[str] = mapped_column(String(500))
    action_taken: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.sysutcdatetime()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(100))
    details: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.sysutcdatetime()
    )
