#!/usr/bin/env python
# QA: Web Push smoke – envía una notificación de prueba a suscripciones existentes.

"""CLI helper to trigger a Web Push test notification."""

from __future__ import annotations

from backend.services.audit_service import AuditService
from backend.services.push_service import endpoint_fingerprint, push_service


def main() -> None:
    if not push_service.has_vapid_keys():
        print("[warn] VAPID keys missing – configure VAPID_PUBLIC_KEY/VAPID_PRIVATE_KEY")
        return

    subscriptions = push_service.get_all_subscriptions()
    if not subscriptions:
        print("[warn] No hay suscripciones push registradas en la base de datos")
        return

    payload = {
        "title": "[QA] Test Web Push",
        "body": "Notificación de depuración enviada desde CLI",
        "url": "/",
    }

    delivered = push_service.broadcast_to_subscriptions(
        subscriptions,
        payload,
        category="system",
    )

    metadata = {
        "delivered": delivered,
        "attempted": len(subscriptions),
        "fingerprints": [endpoint_fingerprint(item.endpoint) for item in subscriptions],
    }

    AuditService.log_event(
        user_id=None,
        action="push.cli_test",
        metadata=metadata,
    )

    if delivered:
        print(f"[ok] Notificaciones Web Push entregadas: {delivered}")
    else:
        print("[warn] No se pudo entregar la notificación – revisa los logs del backend")


if __name__ == "__main__":
    main()
