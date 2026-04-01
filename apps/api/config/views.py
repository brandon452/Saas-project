import logging
import os

from django.conf import settings
from django.db import connection
from django.http import Http404, HttpResponse
from django.views import View
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthView(APIView):
    permission_classes = []

    def get(self, request):
        db_status = "ok"
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            db_status = "down"

        redis_status = "ok"
        try:
            try:
                from django_redis import get_redis_connection
                redis_conn = get_redis_connection("default")
                redis_conn.ping()
            except ImportError:
                # django-redis not installed; use Django's built-in cache backend
                from django.core.cache import cache
                cache.get("__health_check__")
        except Exception:
            logger.error("Redis health check failed", exc_info=True)
            redis_status = "down"

        org = getattr(request, "org", None)
        overall_status = "ok" if db_status == "ok" else "degraded"
        return Response(
            {
                "status": overall_status,
                "organization": org.slug if org else None,
                "db": db_status,
                "redis": redis_status,
            }
        )


class FrontendView(View):
    """Serve Next.js static export entrypoint for non-API routes."""

    def get(self, request, *args, **kwargs):
        index_path = os.path.join(settings.BASE_DIR.parent, "web", "out", "index.html")

        if not os.path.exists(index_path):
            raise Http404("Frontend not built. Run: cd apps/web && npm run build")

        with open(index_path, encoding="utf-8") as f:
            return HttpResponse(f.read(), content_type="text/html")

