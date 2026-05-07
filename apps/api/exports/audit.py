from audit.services import log_audit_event


def log_export_event(*, organization, actor_user, resource, format, filters, row_count=None, document_id=None):
    """
    Log an export audit event.

    For CSV list exports: provide row_count.
    For PDF detail exports: provide document_id.
    """
    metadata = {
        "format": format,
        "resource": resource,
        "filters": filters,
    }
    if row_count is not None:
        metadata["row_count"] = row_count
    if document_id is not None:
        metadata["document_id"] = str(document_id)

    rid = str(document_id) if document_id is not None else "list"
    log_audit_event(
        organization=organization,
        actor_user=actor_user,
        event_type=f"{resource}.exported",
        resource_type=resource,
        resource_id=rid,
        summary=f"Exported {resource} {format.upper()}",
        metadata_json=metadata,
    )
