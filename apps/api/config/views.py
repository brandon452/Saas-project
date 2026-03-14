import os

from django.conf import settings
from django.db import connection
from django.http import Http404, HttpResponse
from django.views import View
from rest_framework.response import Response
from rest_framework.views import APIView


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

        org = getattr(request, "org", None)
        return Response(
            {
                "status": "ok",
                "organization": org.slug if org else None,
                "db": db_status,
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

