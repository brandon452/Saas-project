from .models import Branch


def branches_for_org(organization):
    return Branch.objects.for_org(organization)


def get_branch_for_org(*, branch_id, organization):
    return Branch.objects.get(pk=branch_id, organization=organization)


def get_branch_for_org_or_none(*, branch_id, organization):
    return branches_for_org(organization).filter(pk=branch_id).first()


def get_branch_any_org_or_none(*, branch_id):
    return Branch.all_objects.filter(pk=branch_id).first()


def network_branches_for_org(organization):
    active_org_ids = organization.parent_company.organizations.filter(
        is_active=True,
    ).values_list("pk", flat=True)
    return (
        Branch.objects.filter(organization__in=active_org_ids)
        .select_related("organization")
        .order_by("organization__name", "name")
    )


__all__ = [
    "Branch",
    "branches_for_org",
    "get_branch_any_org_or_none",
    "get_branch_for_org",
    "get_branch_for_org_or_none",
    "network_branches_for_org",
]
