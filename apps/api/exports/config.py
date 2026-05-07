from django.conf import settings


def get_csv_rate() -> str:
    return getattr(settings, "EXPORT_CSV_RATE_LIMIT", "20/m")


def get_pdf_rate() -> str:
    return getattr(settings, "EXPORT_PDF_RATE_LIMIT", "10/m")


def get_max_rows() -> int:
    return getattr(settings, "EXPORT_MAX_ROWS", 10000)
