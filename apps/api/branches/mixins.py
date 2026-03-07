from rest_framework.exceptions import ValidationError


class BranchRequiredMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not getattr(request, "branch", None):
            raise ValidationError({"detail": "X-BRANCH-ID header required"})