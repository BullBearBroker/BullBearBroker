"""Normalize persisted enum values to match current canonical options."""

import logging

from backend.database import SessionLocal
from backend.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def normalize_risk_profiles() -> None:
    """Normalize stored risk_profile values to uppercase enum names."""

    session = SessionLocal()
    try:
        users = session.query(User).all()
        fixed = 0
        valid_values = {"CONSERVADOR", "MODERADO", "AGRESIVO"}

        for user in users:
            current = user.risk_profile
            if not current:
                continue

            normalized = current.upper()
            if normalized not in valid_values:
                logger.warning(
                    "Valor desconocido '%s' en usuario %s", current, user.email
                )
                continue

            if normalized != current:
                logger.info("Corrigiendo %s: %s → %s", user.email, current, normalized)
                user.risk_profile = normalized
                fixed += 1

        if fixed:
            session.commit()
            logger.info(
                "✅ Se corrigieron %s usuarios con risk_profile normalizado.", fixed
            )
        else:
            logger.info("No se detectaron perfiles en minúsculas o inválidos.")

    except Exception as exc:  # pragma: no cover - mantenimiento manual
        logger.error("Error al normalizar risk_profile: %s", exc)
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    normalize_risk_profiles()
