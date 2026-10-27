from sqlalchemy.orm import Session

from app.models import AuditLog, User


def record_audit(
    database: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: str | int,
    details: str | None = None,
) -> None:
    database.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=details,
        )
    )
