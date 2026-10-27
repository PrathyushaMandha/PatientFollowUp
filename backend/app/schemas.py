from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserView(OrmModel):
    id: int
    username: str
    role: str
    patient_id: int | None


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)
    role: str = Field(pattern="^(admin|clinician)$")


class PatientSignup(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date | None = None
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)


class PatientCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    date_of_birth: date | None = None
    portal_username: str | None = Field(default=None, min_length=3, max_length=100)
    portal_password: str | None = Field(default=None, min_length=10, max_length=128)

    @model_validator(mode="after")
    def validate_portal_credentials(self) -> "PatientCreate":
        if bool(self.portal_username) != bool(self.portal_password):
            raise ValueError("Portal username and password must be provided together")
        return self


class PatientView(OrmModel):
    public_id: str
    first_name: str
    last_name: str
    date_of_birth: datetime | None
    is_active: bool
    created_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class MessageView(OrmModel):
    id: int
    chat_session_id: str
    role: str
    content: str
    sequence_number: int
    flagged: bool
    created_at: datetime


class ConsultationView(OrmModel):
    public_id: str
    patient_id: int
    status: str
    started_at: datetime
    ended_at: datetime | None
    requires_review: bool
    has_assessment: bool
    messages: list[MessageView] = []


class QuestionView(BaseModel):
    number: int
    text: str
    answer_options: list[str]


class AssessmentStartResponse(OrmModel):
    public_id: str
    status: str
    next_question: QuestionView


class AnswerCreate(BaseModel):
    question_number: int = Field(ge=1, le=9)
    score: int = Field(ge=0, le=3)


class AnswerView(OrmModel):
    question_number: int
    question_text: str
    score: int
    answer_text: str


class AssessmentView(OrmModel):
    public_id: str
    instrument: str
    status: str
    total_score: int | None
    severity: str | None
    started_at: datetime
    completed_at: datetime | None
    answers: list[AnswerView] = []


class AnswerResult(BaseModel):
    assessment: AssessmentView
    next_question: QuestionView | None
    safety_alert: bool = False
    safety_message: str | None = None


class AssessmentComparison(BaseModel):
    assessment: AssessmentView
    score_change: int | None
    answer_changes: dict[int, int]


class SummaryView(OrmModel):
    id: int
    consultation_id: int
    content: str
    generated_by: str
    review_status: str
    reviewed_at: datetime | None
    created_at: datetime


class SummaryReview(BaseModel):
    review_status: str = Field(pattern="^(approved|rejected)$")


class SafetyEventView(OrmModel):
    id: int
    consultation_id: int
    reason: str
    action_taken: str
    status: str
    created_at: datetime
    resolved_at: datetime | None


class SafetyUpdate(BaseModel):
    status: str = Field(pattern="^(acknowledged|resolved)$")
