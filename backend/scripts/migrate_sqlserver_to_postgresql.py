import argparse
import os
from collections.abc import Mapping, Sequence
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import MetaData, create_engine, delete, func, insert, select, text, update
from sqlalchemy.engine import Connection, Engine

from app.config import Settings, get_settings


APPLICATION_TABLES = (
    "assessment_answers",
    "assessments",
    "audit_logs",
    "consultation_summaries",
    "consultations",
    "messages",
    "patients",
    "safety_events",
    "users",
    "voice_recordings",
)
COPY_ORDER = (
    "users",
    "patients",
    "consultations",
    "messages",
    "assessments",
    "assessment_answers",
    "consultation_summaries",
    "safety_events",
    "audit_logs",
)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def prepare_user_rows(
    rows: Sequence[Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[int, int]]:
    prepared_rows = [dict(row) for row in rows]
    patient_links: dict[int, int] = {}
    for row in prepared_rows:
        patient_id = row.get("patient_id")
        if patient_id is not None:
            patient_links[int(row["id"])] = int(patient_id)
            row["patient_id"] = None
    return prepared_rows, patient_links


def validate_dialects(source_dialect: str, target_dialect: str) -> None:
    if source_dialect != "mssql":
        raise RuntimeError("Source database must be Microsoft SQL Server")
    if target_dialect != "postgresql":
        raise RuntimeError("Target database must be PostgreSQL")


def table_counts(connection: Connection, metadata: MetaData) -> dict[str, int]:
    return {
        table_name: int(
            connection.scalar(
                select(func.count()).select_from(metadata.tables[table_name])
            )
            or 0
        )
        for table_name in APPLICATION_TABLES
    }


def reflect_schema(engine: Engine) -> MetaData:
    metadata = MetaData()
    metadata.reflect(bind=engine, only=APPLICATION_TABLES)
    missing_tables = set(APPLICATION_TABLES) - set(metadata.tables)
    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise RuntimeError(f"Database is missing required tables: {missing}")
    return metadata


def reset_postgresql_sequence(connection: Connection, table_name: str) -> None:
    quoted_table = connection.dialect.identifier_preparer.quote(table_name)
    connection.execute(
        text(
            "SELECT setval("
            "pg_get_serial_sequence(:table_name, 'id'), "
            f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM {quoted_table}"
        ),
        {"table_name": table_name},
    )


def replace_target_data(source_engine: Engine, target_engine: Engine) -> dict[str, int]:
    source_metadata = reflect_schema(source_engine)
    target_metadata = reflect_schema(target_engine)

    with source_engine.connect() as source, target_engine.begin() as target:
        quoted_tables = ", ".join(
            target.dialect.identifier_preparer.quote(table_name)
            for table_name in APPLICATION_TABLES
        )
        target.execute(text(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE"))

        copied_counts: dict[str, int] = {}
        patient_links: dict[int, int] = {}
        for table_name in COPY_ORDER:
            source_table = source_metadata.tables[table_name]
            target_table = target_metadata.tables[table_name]
            rows = list(source.execute(select(source_table)).mappings())
            if table_name == "users":
                prepared_rows, patient_links = prepare_user_rows(rows)
            else:
                prepared_rows = [dict(row) for row in rows]
            if prepared_rows:
                target.execute(insert(target_table), prepared_rows)
            copied_counts[table_name] = len(prepared_rows)

        users = target_metadata.tables["users"]
        for user_id, patient_id in patient_links.items():
            target.execute(
                update(users)
                .where(users.c.id == user_id)
                .values(patient_id=patient_id)
            )

        voice_recordings = target_metadata.tables["voice_recordings"]
        target.execute(delete(voice_recordings))
        copied_counts["voice_recordings"] = 0

        for table_name in APPLICATION_TABLES:
            reset_postgresql_sequence(target, table_name)

    return copied_counts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace PostgreSQL application data with local SQL Server data."
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive MIGRATE confirmation.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(BACKEND_ROOT / ".env", override=False)
    target_url = os.getenv("TARGET_DATABASE_URL")
    if not target_url:
        raise RuntimeError("TARGET_DATABASE_URL is required")

    source_engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    target_settings = Settings(database_url=target_url, _env_file=None)
    target_engine = create_engine(target_settings.database_url, pool_pre_ping=True)
    validate_dialects(source_engine.dialect.name, target_engine.dialect.name)

    source_metadata = reflect_schema(source_engine)
    target_metadata = reflect_schema(target_engine)
    with source_engine.connect() as source, target_engine.connect() as target:
        source_counts = table_counts(source, source_metadata)
        target_counts = table_counts(target, target_metadata)

    print("Source SQL Server rows:")
    for table_name, count in source_counts.items():
        print(f"  {table_name}: {count}")
    print("Current PostgreSQL rows that will be replaced:")
    for table_name, count in target_counts.items():
        print(f"  {table_name}: {count}")
    print("Voice recording metadata will not be copied because audio files stay local.")

    if not args.yes and input("Type MIGRATE to continue: ").strip() != "MIGRATE":
        print("Migration cancelled.")
        return 1

    copied_counts = replace_target_data(source_engine, target_engine)
    print("Migration completed:")
    for table_name, count in copied_counts.items():
        print(f"  {table_name}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
