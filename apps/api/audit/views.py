import csv
import json
from datetime import timezone as dt_timezone

from django.http import StreamingHttpResponse
from django.utils.dateparse import parse_datetime
from rest_framework import generics
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from tenancy.models import Organization
from tenancy.permissions import IsOrgOwnerOrAdminOrParentAdmin

from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventListView(generics.ListAPIView):
    serializer_class = AuditEventSerializer
    permission_classes = [IsAuthenticated, IsOrgOwnerOrAdminOrParentAdmin]

    def initial(self, request, *args, **kwargs):
        org_id = kwargs.get("org_id")
        try:
            request.org = Organization.objects.select_related("parent_company").get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")
        super().initial(request, *args, **kwargs)

    def _parse_utc_datetime(self, value: str | None, field_name: str):
        if not value:
            return None
        parsed = parse_datetime(value)
        if parsed is None:
            raise ValidationError({field_name: "Enter a valid ISO-8601 datetime."})
        if parsed.tzinfo is None:
            raise ValidationError({field_name: "Datetime must include timezone (UTC ISO-8601)."})
        return parsed

    def get_queryset(self):
        qs = AuditEvent.objects.filter(organization=self.request.org).select_related("actor_user")
        params = self.request.query_params

        event_type = params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        resource_type = params.get("resource_type")
        if resource_type:
            qs = qs.filter(resource_type=resource_type)

        resource_id = params.get("resource_id")
        if resource_id:
            qs = qs.filter(resource_id=resource_id)

        actor_user_id = params.get("actor_user_id")
        if actor_user_id:
            qs = qs.filter(actor_user_id=actor_user_id)

        q = params.get("q")
        if q:
            qs = qs.filter(summary__icontains=q)

        dt_from = self._parse_utc_datetime(params.get("from"), "from")
        if dt_from:
            qs = qs.filter(occurred_at__gte=dt_from)

        dt_to = self._parse_utc_datetime(params.get("to"), "to")
        if dt_to:
            qs = qs.filter(occurred_at__lte=dt_to)

        return qs.order_by("-occurred_at")


class _Echo:
    def write(self, value):
        return value


class AuditEventExportView(APIView):
    permission_classes = [IsAuthenticated, IsOrgOwnerOrAdminOrParentAdmin]
    MAX_EXPORT_ROWS = 10000

    def initial(self, request, *args, **kwargs):
        org_id = kwargs.get("org_id")
        try:
            request.org = Organization.objects.select_related("parent_company").get(pk=org_id, is_active=True)
        except Organization.DoesNotExist:
            raise NotFound("Organization not found.")
        super().initial(request, *args, **kwargs)

    def _parse_utc_datetime(self, value: str | None, field_name: str):
        if not value:
            return None
        parsed = parse_datetime(value)
        if parsed is None:
            raise ValidationError({field_name: "Enter a valid ISO-8601 datetime."})
        if parsed.tzinfo is None:
            raise ValidationError({field_name: "Datetime must include timezone (UTC ISO-8601)."})
        return parsed

    def _get_queryset(self):
        qs = AuditEvent.objects.filter(organization=self.request.org).select_related("actor_user")
        params = self.request.query_params

        event_type = params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        resource_type = params.get("resource_type")
        if resource_type:
            qs = qs.filter(resource_type=resource_type)

        resource_id = params.get("resource_id")
        if resource_id:
            qs = qs.filter(resource_id=resource_id)

        actor_user_id = params.get("actor_user_id")
        if actor_user_id:
            qs = qs.filter(actor_user_id=actor_user_id)

        q = params.get("q")
        if q:
            qs = qs.filter(summary__icontains=q)

        dt_from = self._parse_utc_datetime(params.get("from"), "from")
        if dt_from:
            qs = qs.filter(occurred_at__gte=dt_from)

        dt_to = self._parse_utc_datetime(params.get("to"), "to")
        if dt_to:
            qs = qs.filter(occurred_at__lte=dt_to)

        return qs.order_by("-occurred_at")

    def get(self, request, *args, **kwargs):
        qs = self._get_queryset()
        total = qs.count()
        if total > self.MAX_EXPORT_ROWS:
            raise ValidationError(
                {"detail": f"Too many rows to export ({total}). Please narrow your filters below {self.MAX_EXPORT_ROWS} rows."}
            )

        pseudo_buffer = _Echo()
        writer = csv.writer(pseudo_buffer)

        headers = [
            "occurred_at",
            "event_type",
            "resource_type",
            "resource_id",
            "actor_type",
            "actor_user_id",
            "actor_name_snapshot",
            "actor_email_snapshot",
            "summary",
            "diff_json",
            "metadata_json",
        ]

        def iter_rows():
            yield writer.writerow(headers)
            for event in qs.iterator(chunk_size=1000):
                occurred_at = event.occurred_at.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")
                diff_json = json.dumps(event.diff_json, separators=(",", ":"), ensure_ascii=False)
                metadata_json = json.dumps(event.metadata_json, separators=(",", ":"), ensure_ascii=False)
                yield writer.writerow(
                    [
                        occurred_at,
                        event.event_type,
                        event.resource_type,
                        event.resource_id,
                        event.actor_type,
                        str(event.actor_user_id or ""),
                        event.actor_name_snapshot,
                        event.actor_email_snapshot,
                        event.summary,
                        diff_json,
                        metadata_json,
                    ]
                )

        response = StreamingHttpResponse(iter_rows(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit-events.csv"'
        return response
