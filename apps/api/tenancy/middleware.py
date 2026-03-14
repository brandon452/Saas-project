from branches.models import Branch


class BranchContextMiddleware:
    """
    Sets request.branch from X-BRANCH-ID header.
    Org resolution is handled in OrgScopedViewSetMixin via URL kwargs.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        branch_id = request.headers.get("X-BRANCH-ID")
        request.branch = None

        if branch_id:
            try:
                request.branch = Branch.objects.select_related("organization").get(pk=branch_id)
            except (Branch.DoesNotExist, ValueError):
                request.branch = None

        return self.get_response(request)
