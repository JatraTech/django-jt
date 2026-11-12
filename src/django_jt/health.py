"""
Health check endpoints for orchestration (k8s liveness/readiness probes,
load-balancer health checks, post-deploy smoke tests).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@csrf_exempt
@require_GET
def liveness(request):
    """Cheap process check; does not hit downstream dependencies."""
    return JsonResponse({"status": "alive"})


@csrf_exempt
@require_GET
def readiness(request):
    """
    Readiness probe: Postgres plus optional Redis Celery broker.
    Returns 503 when a critical dependency is down.
    """
    checks: dict[str, str] = {}
    overall_ok = True

    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
        checks["database"] = "up" if row == (1,) else "degraded"
    except Exception as exc:  # noqa: BLE001
        checks["database"] = "down"
        overall_ok = False
        logger.warning("Readiness DB check failed: %s", exc)

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        checks["broker"] = "eager"
    elif broker_url := getattr(settings, "CELERY_BROKER_URL", ""):
        if broker_url.startswith("redis://"):
            try:
                import redis

                r = redis.from_url(broker_url, socket_connect_timeout=2)
                r.ping()
                checks["broker"] = "up"
            except Exception as exc:  # noqa: BLE001
                checks["broker"] = "down"
                overall_ok = False
                logger.warning("Readiness broker check failed: %s", exc)
        else:
            checks["broker"] = "skipped"
    else:
        checks["broker"] = "skipped"

    body = {
        "status": "ready" if overall_ok else "not_ready",
        "checks": checks,
    }
    return JsonResponse(body, status=200 if overall_ok else 503)
