import json
import logging
from copy import deepcopy
from typing import Any

from .models import AuditEvent

logger = logging.getLogger(__name__)

MAX_METADATA_BYTES = 16 * 1024
MAX_DIFF_BYTES = 16 * 1024
MAX_STRING_CHARS = 512


def actor_snapshot(user) -> tuple[str, str]:
    if not user:
        return "", ""
    email = getattr(user, "email", "") or ""
    full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    if not full_name:
        full_name = getattr(user, "username", "") or email
    return email, full_name


def _trim_large_strings(payload: Any, truncated_fields: list[str], path: str = "") -> Any:
    if isinstance(payload, dict):
        return {key: _trim_large_strings(value, truncated_fields, f"{path}.{key}" if path else key) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_trim_large_strings(value, truncated_fields, f"{path}[{index}]") for index, value in enumerate(payload)]
    if isinstance(payload, str) and len(payload) > MAX_STRING_CHARS:
        truncated_fields.append(path or "<root>")
        return payload[:MAX_STRING_CHARS]
    return payload


def _bounded_json(payload: Any, max_bytes: int, key_name: str) -> Any:
    original = payload if payload is not None else {}
    safe_payload = deepcopy(original)
    truncated_fields: list[str] = []
    safe_payload = _trim_large_strings(safe_payload, truncated_fields)
    encoded = json.dumps(safe_payload, default=str)
    if len(encoded.encode("utf-8")) <= max_bytes:
        return safe_payload

    return {
        "truncated": True,
        "reason": f"{key_name} exceeded size limit",
        "truncated_fields": truncated_fields,
    }


def changed_field_diff(before: dict[str, Any], after: dict[str, Any], fields: list[str]) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for field in fields:
        before_value = before.get(field)
        after_value = after.get(field)
        if before_value != after_value:
            diff[field] = {"before": before_value, "after": after_value}
    return diff


def log_audit_event(
    *,
    organization,
    actor_user,
    event_type: str,
    resource_type: str,
    resource_id: Any,
    summary: str,
    metadata_json: dict[str, Any] | None = None,
    diff_json: dict[str, Any] | None = None,
) -> None:
    actor_type = AuditEvent.ACTOR_TYPE_SYSTEM if actor_user is None else AuditEvent.ACTOR_TYPE_USER
    email_snapshot, name_snapshot = actor_snapshot(actor_user)
    bounded_metadata = _bounded_json(metadata_json or {}, MAX_METADATA_BYTES, "metadata_json")
    bounded_diff = None if diff_json is None else _bounded_json(diff_json, MAX_DIFF_BYTES, "diff_json")

    try:
        AuditEvent.objects.create(
            organization=organization,
            actor_user=actor_user,
            actor_type=actor_type,
            actor_email_snapshot=email_snapshot,
            actor_name_snapshot=name_snapshot,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=str(resource_id),
            summary=summary[:255],
            metadata_json=bounded_metadata,
            diff_json=bounded_diff,
        )
    except Exception:
        logger.exception(
            "Audit log write failed (org=%s event=%s resource=%s:%s)",
            getattr(organization, "id", None),
            event_type,
            resource_type,
            resource_id,
        )
