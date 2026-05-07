from datetime import timezone as dt_timezone

HEADERS = [
    "id",
    "status",
    "from_branch",
    "to_branch",
    "from_org",
    "to_org",
    "created_at",
    "notes",
]


def to_row(transfer):
    created_at = transfer.created_at.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")
    return [
        str(transfer.id),
        transfer.status,
        transfer.from_branch.name if transfer.from_branch_id else "",
        transfer.to_branch.name if transfer.to_branch_id else "",
        transfer.organization.name if transfer.organization_id else "",
        transfer.to_organization.name if transfer.to_organization_id else "",
        created_at,
        transfer.notes,
    ]
