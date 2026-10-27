# Project Summary for BRD Generation

## Project Name

Continuum Patient Follow-up AI Agent

## Summary

Continuum is a full-stack healthcare follow-up prototype that helps clinicians and patients manage ongoing consultations. It preserves patient-specific history, conducts PHQ-9 assessments, compares results across visits, generates context-aware follow-up questions, identifies concerning responses, and creates consultation summaries and PDF reports.

The platform is not a general chatbot, diagnostic tool, medical device, or emergency service. AI supports conversational wording and symptom extraction, while deterministic backend logic controls authentication, authorization, PHQ-9 scoring, validation, consultation state, and safety escalation. Clinical decisions remain with qualified professionals.

## Users

- **Administrator:** Manages users and has system-wide oversight.
- **Clinician:** Creates patients, starts consultations, reviews history, approves summaries, and handles safety events.
- **Patient:** Accesses only their own records, participates through text or voice, completes assessments, and downloads reports.

## Main Workflow

1. A patient self-registers or a clinician creates the patient and portal account.
2. The user signs in using username and password.
3. An authorized user starts a consultation for the patient.
4. The backend retrieves previous assessments, approved summaries, and relevant patient statements.
5. Groq generates a personalized opening question.
6. The patient responds through text or browser-based voice.
7. Messages and transcripts are stored in SQL Server.
8. The backend checks responses for defined safety concerns.
9. If safe, Groq generates the next contextual follow-up question.
10. When required, the patient completes the nine PHQ-9 questions one at a time.
11. The backend validates answers, calculates the score and severity, and compares previous results.
12. A positive PHQ-9 question 9 response or concerning chat language creates a safety event for clinician review.
13. Completing the consultation creates a draft summary.
14. The clinician approves or rejects the summary.
15. An authorized user can generate a PDF report containing patient details, assessment results, symptom findings, and the approved summary.
16. The stored history is used to personalize future consultations.

## Main Features

- JWT authentication and role-based access control.
- Patient registration and separate patient portal accounts.
- Persistent consultations and conversation history.
- Groq-generated opening and follow-up questions.
- Browser speech-to-text and text-to-speech interaction.
- PHQ-9 questionnaire, validation, scoring, severity, and history comparison.
- Deterministic safety detection and clinician review queue.
- Draft consultation summaries with approval and rejection workflow.
- PDF consultation reports without full conversation or audio transcripts.
- Audit logging for authentication and clinical workflow actions.
- Responsive React interface for clinicians and patients.

## Technology Stack

### Frontend

- React 19
- TypeScript 5.9
- Vite 7
- Axios
- Lucide React
- CSS
- Browser Web Speech API
- Browser Speech Synthesis API
- ESLint

### Backend

- Python
- FastAPI
- Uvicorn
- SQLAlchemy 2
- Alembic
- Pydantic Settings
- python-jose with JWT
- pwdlib with Argon2 password hashing
- Groq SDK
- ReportLab and PyPDF
- Pytest and pytest-asyncio

### Database and Integration

- Microsoft SQL Server
- pyODBC with ODBC Driver 18
- Groq LLM API
- REST and JSON APIs
- JWT bearer authentication

## Core Data

The application stores users, patients, consultations, messages, PHQ-9 assessments, assessment answers, consultation summaries, safety events, and audit logs. Only one active consultation is allowed for each patient, while completed consultations and assessments remain available for historical comparison.

## Safety and Privacy

- A positive answer to PHQ-9 question 9 creates a safety event.
- Defined concerning chat phrases also create a safety event.
- The patient receives an approved immediate-support message.
- Clinicians can acknowledge and resolve safety events.
- The system does not automatically contact emergency services.
- Email and phone redaction before AI processing is limited and is not complete de-identification.
- Real-patient use requires approved consent, privacy, security, retention, clinical escalation, and AI-provider agreements.
- Development and testing should use synthetic patient information.

## Current Constraints

- Groq is required for conversational responses and report symptom extraction.
- Voice capability depends on browser and operating-system support.
- The system does not provide diagnosis or treatment recommendations.
- There is no EHR, billing, insurance, medication, SMS, email, or emergency-service integration.
- The current application is a development prototype and requires production hardening and clinical approval.

## Expected Business Value

The project centralizes patient follow-up history, reduces repeated questioning, automates structured assessment scoring, highlights changes across visits, supports earlier review of concerning responses, and provides clinicians and patients with a consistent record of follow-up activity.