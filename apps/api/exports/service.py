from dataclasses import dataclass
from typing import Callable, Iterable

from django.core.exceptions import ImproperlyConfigured
from django.http import StreamingHttpResponse
from rest_framework.exceptions import Throttled

from .audit import log_export_event
from .config import get_csv_rate
from .filenames import csv_filename
from .streaming import enforce_row_cap, stream_csv


@dataclass(frozen=True)
class ExportConfig:
    headers: list[str]
    filename_prefix: str
    rate_group: str
    audit_resource: str
    row_cap: int | None = None
    filters_provider: Callable | None = None
    require_ordering: bool = True


class ExportService:
    @staticmethod
    def export_stream(
        *,
        request,
        queryset,
        config: ExportConfig,
        row_iter: Iterable,
        organization,
        rate_limiter=None,
    ) -> StreamingHttpResponse:
        if rate_limiter and rate_limiter(
            request,
            group=config.rate_group,
            key="user",
            rate=get_csv_rate(),
            method="GET",
            increment=True,
        ):
            raise Throttled(detail="Too many export requests. Please wait before exporting again.")

        if config.require_ordering and getattr(queryset, "ordered", True) is False:
            raise ImproperlyConfigured("CSV exports require deterministic queryset ordering.")

        row_count = enforce_row_cap(queryset, max_rows=config.row_cap)
        filters = config.filters_provider(request) if config.filters_provider else dict(request.query_params)
        log_export_event(
            organization=organization,
            actor_user=request.user,
            resource=config.audit_resource,
            format="csv",
            filters=filters,
            row_count=row_count,
        )
        return stream_csv(config.headers, row_iter, csv_filename(config.filename_prefix))
