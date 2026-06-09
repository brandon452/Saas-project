import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)
export_config_invalid_total = 0


def get_csv_rate() -> str:
    return getattr(settings, "EXPORT_CSV_RATE_LIMIT", "20/m")


def get_pdf_rate() -> str:
    return getattr(settings, "EXPORT_PDF_RATE_LIMIT", "10/m")


def get_max_rows() -> int:
    return getattr(settings, "EXPORT_MAX_ROWS", 10000)


def get_export_csv_service_enabled() -> bool:
    return getattr(settings, "EXPORT_CSV_SERVICE_ENABLED", False)


def get_export_csv_endpoint_overrides() -> dict[str, bool]:
    return parse_export_csv_endpoint_overrides(
        getattr(settings, "EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES", {}),
        production=not getattr(settings, "DEBUG", False),
    )


def parse_export_csv_endpoint_overrides(raw, *, production: bool) -> dict[str, bool]:
    if raw in (None, ""):
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            return _handle_invalid_overrides(exc, production=production)
    if not isinstance(raw, dict) or any(not isinstance(key, str) or not isinstance(value, bool) for key, value in raw.items()):
        return _handle_invalid_overrides(ValueError("override map must be {endpoint: bool}"), production=production)
    return dict(raw)


def validate_export_config():
    get_export_csv_endpoint_overrides()


def _handle_invalid_overrides(exc: Exception, *, production: bool) -> dict[str, bool]:
    global export_config_invalid_total
    if not production:
        raise ValueError("Invalid EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES") from exc

    export_config_invalid_total += 1
    logger.error("Invalid EXPORT_CSV_SERVICE_ENDPOINT_OVERRIDES; falling back to {}", exc_info=exc)
    try:
        import sentry_sdk
    except ImportError:
        sentry_sdk = None
    if sentry_sdk:
        sentry_sdk.capture_exception(exc)
    return {}
