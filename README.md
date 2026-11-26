# Continuum Patient Follow-up

Continuum is a full-stack patient follow-up application built with FastAPI, React, and SQL Server. It supports clinician and patient accounts, consultation history, PHQ-9 assessments, safety escalation, and AI-generated follow-up conversations through Groq.

## Prerequisites

Install the following before starting:

- Git
- Python 3.10 or newer
- Node.js 20.19 or newer with npm
- SQL Server
- Microsoft ODBC Driver 18 for SQL Server
- A Groq API key for consultation conversations

The default database connection uses Windows authentication and expects SQL Server at `localhost`.

## 1. Clone the repository

Replace `<repository-url>` with this project's Git repository URL:

```powershell
git clone <repository-url>
Set-Location AIAgent
```

If the cloned directory has a different name, use that name in the `Set-Location` command.

## 2. Create the SQL Server database

Create an empty database named `PatientFollowup`. Run the following SQL in SQL Server Management Studio:

```sql
IF DB_ID('PatientFollowup') IS NULL
BEGIN
	CREATE DATABASE PatientFollowup;
END;
```

The default connection is:

```text
Server: localhost
Database: PatientFollowup
Authentication: Windows authentication
Driver: ODBC Driver 18 for SQL Server
```

To use another server, database, or authentication method, update `DATABASE_URL` in `backend/.env`.

For a PostgreSQL production database, set `DATABASE_URL` to the provider's
`postgresql://...` connection string. The application automatically selects the
installed Psycopg driver.

To replace an empty PostgreSQL deployment with existing local SQL Server data,
set `TARGET_DATABASE_URL` in `backend/.env`, then run:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m scripts.migrate_sqlserver_to_postgresql
```

The command displays source and target row counts and requires `MIGRATE`
confirmation. It preserves password hashes but excludes voice-recording metadata
because local audio files are not deployed with the application.

## 3. Install the backend

From the repository root, create a virtual environment and install the Python dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Copy-Item backend\.env.example backend\.env
```

Open `backend/.env` and set at least these values:

```dotenv
SECRET_KEY=replace-with-a-long-random-value
GROQ_API_KEY=your-groq-api-key
```

Keep the provided `DATABASE_URL` if the default local SQL Server configuration matches your environment.

Apply the database migrations:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ..
```

## 4. Install the frontend

```powershell
Set-Location frontend
npm install
Set-Location ..
```

## 5. Run the application

Start the backend from the repository root:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

In a second PowerShell terminal, start the frontend:

```powershell
Set-Location <path-to-AIAgent>\frontend
npm run dev
```

Open `http://localhost:5173` in a browser. API documentation is available at `http://127.0.0.1:8000/docs`.

## 6. Create the initial account

With the backend running, execute this once in another PowerShell terminal:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/bootstrap
```

Then sign in through the frontend with the development credentials from `backend/.env`:

```text
Username: clinician
Password: ChangeMe123!
```

The bootstrap endpoint works only while the user table is empty. Change the bootstrap password before using the application outside local development.

## Verification

Run backend tests:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
```

Run frontend checks:

```powershell
Set-Location frontend
npm run lint
npm run build
```

## Troubleshooting

- **Database connection fails:** Confirm SQL Server is running, the `PatientFollowup` database exists, and ODBC Driver 18 is installed.
- **The API reports `missing_key`:** Add a valid `GROQ_API_KEY` to `backend/.env`, then restart the backend.
- **Port already in use:** Stop the process using port `8000` or `5173`, or start the service on another port and update the related configuration.
- **Bootstrap returns HTTP 409:** An account already exists; sign in with the configured credentials instead of running bootstrap again.

## Clinical boundary

This repository is a development prototype, not a medical device or emergency service. Do not use identifiable patient information with an AI provider without approved data-handling agreements. Clinical teams must approve escalation wording, consent, access control, encryption, audit retention, and emergency procedures before real-patient use.

Patient voice sessions save the searchable transcript in SQL Server and microphone audio under `backend/voice_recordings/`. Audio downloads require an authenticated user with access to the consultation. Production deployments must move recordings to encrypted managed storage and define explicit consent, retention, deletion, and backup policies.