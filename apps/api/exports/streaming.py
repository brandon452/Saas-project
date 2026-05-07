import csv

from django.http import StreamingHttpResponse
from rest_framework.exceptions import ValidationError

from .config import get_max_rows


class _Echo:
    """Pseudo-buffer used with csv.writer for StreamingHttpResponse."""
    def write(self, value):
        return value


def stream_csv(headers, row_iter, filename):
    """
    Return a StreamingHttpResponse for a CSV export.

    headers   - list of column header strings
    row_iter  - iterable of lists (one per data row)
    filename  - Content-Disposition filename (e.g. "purchase-orders-2025-01-01.csv")
    """
    pseudo_buffer = _Echo()
    writer = csv.writer(pseudo_buffer)

    def _iter():
        yield writer.writerow(headers)
        for row in row_iter:
            yield writer.writerow(row)

    response = StreamingHttpResponse(_iter(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def enforce_row_cap(queryset):
    """
    Raise a friendly ValidationError if the queryset exceeds EXPORT_MAX_ROWS.
    Returns the count for use in audit logging.
    """
    max_rows = get_max_rows()
    total = queryset.count()
    if total > max_rows:
        raise ValidationError(
            {"detail": f"Too many rows to export ({total}). Please narrow your filters below {max_rows} rows."}
        )
    return total
