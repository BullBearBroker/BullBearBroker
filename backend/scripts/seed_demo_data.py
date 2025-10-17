# QA 2.5: Demo data for local staging verification (user, portfolio, alerts)

from __future__ import annotations

# QA 3.0: evitar literales de secreto en seed
import os
from datetime import datetime

from backend.database import SessionLocal
from backend.models.alert import Alert, AlertDeliveryMethod
from backend.models.portfolio import Portfolio
from backend.models.user import RiskProfileEnum, User

# Donde antes había un valor sensible, usar env con default inocuo:
DEMO_ALERT_SECRET = os.getenv(
    "DEMO_ALERT_SECRET", "placeholder"
)  # pragma: allowlist secret


# QA 2.5: Seed demo data
def main() -> None:
    db = SessionLocal()

    try:
        # 1️⃣ Usuario de prueba
        user = db.query(User).filter_by(email="test@bullbear.ai").first()
        if not user:
            user = User(
                email="test@bullbear.ai",
                password_hash="demo-hash",  # pragma: allowlist secret
                risk_profile=RiskProfileEnum.MODERADO.value,
                mfa_enabled=False,
                created_at=datetime.utcnow(),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"🧩 Usuario creado: {user.email}")
        else:
            print(f"🧩 Usuario existente reutilizado: {user.email}")

        # 2️⃣ Portafolio demo
        portfolio = (
            db.query(Portfolio)
            .filter_by(user_id=user.id, name="Portafolio Demo")
            .first()
        )
        if not portfolio:
            portfolio = Portfolio(
                user_id=user.id,
                name="Portafolio Demo",
                created_at=datetime.utcnow(),
            )
            db.add(portfolio)
            db.commit()
            print("📊 Portafolio demo creado")
        else:
            print("📊 Portafolio demo existente reutilizado")

        # 3️⃣ Alerta o notificación simple
        alert = (
            db.query(Alert).filter_by(user_id=user.id, name="Alerta AAPL Demo").first()
        )
        if not alert:
            alert = Alert(
                user_id=user.id,
                name="Alerta AAPL Demo",
                condition={
                    "type": "price_above",
                    "symbol": "AAPL",
                    "target": 180.0,
                    "demo_secret": DEMO_ALERT_SECRET,
                },
                delivery_method=AlertDeliveryMethod.PUSH,
                active=True,
                pending_delivery=True,
                created_at=datetime.utcnow(),
                asset="AAPL",
                condition_expression="price > 180",
                value=180.0,
            )
            db.add(alert)
            db.commit()
            print("🚨 Alerta de prueba creada")
        else:
            print("🚨 Alerta de prueba existente reutilizada")

    finally:
        db.close()

    print("✅ QA 2.5: Seed demo data completed")


if __name__ == "__main__":
    main()
