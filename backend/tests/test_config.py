from app.config import Settings


def test_plain_postgresql_url_uses_psycopg_driver() -> None:
    settings = Settings(
        database_url="postgresql://user:password@example.com/database",
        _env_file=None,
    )

    assert (
        settings.database_url
        == "postgresql+psycopg://user:password@example.com/database"
    )


def test_non_postgresql_url_is_unchanged() -> None:
    database_url = "mssql+pyodbc://@localhost/database"
    settings = Settings(database_url=database_url, _env_file=None)

    assert settings.database_url == database_url
