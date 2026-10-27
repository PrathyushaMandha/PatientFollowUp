from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Patient Follow-up API"
    environment: str = "development"
    database_url: str = (
        "mssql+pyodbc://@localhost/PatientFollowup?"
        "driver=ODBC+Driver+18+for+SQL+Server&"
        "Trusted_Connection=yes&TrustServerCertificate=yes"
    )
    secret_key: str = "change-this-secret-before-deployment"
    access_token_minutes: int = 480
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    patient_default_password: str = "prathyu@315"
    frontend_origin: str = "http://localhost:5173"
    bootstrap_username: str = "clinician"
    bootstrap_password: str = "ChangeMe123!"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
