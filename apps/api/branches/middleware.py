from uuid import UUID

from django.http import JsonResponse

from .models import Branch


class BranchMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if getattr(request, "org", None) is None:
            request.branch = None
            return self.get_response(request)

        branch_header = request.headers.get("X-BRANCH-ID")
        if not branch_header:
            request.branch = None
            return self.get_response(request)

        try:
            branch_uuid = UUID(branch_header)
        except ValueError:
            return JsonResponse({"detail": "Branch not found"}, status=400)

        branch = Branch.objects.for_org(request.org).filter(id=branch_uuid).first()
        if branch:
            request.branch = branch
            return self.get_response(request)

        branch_any_org = Branch.all_objects.filter(id=branch_uuid).first()
        if branch_any_org:
            return JsonResponse({"detail": "Branch does not belong to organization"}, status=403)

        return JsonResponse({"detail": "Branch not found"}, status=400)
