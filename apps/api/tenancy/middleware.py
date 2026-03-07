import re

from django.core.exceptions import DisallowedHost
from django.http import JsonResponse

from .context import current_org, in_request_context
from .models import Organization


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            host = request.get_host().split(":")[0]
        except DisallowedHost:
            raw_host = request.META.get("HTTP_HOST", "")
            fallback_host = raw_host.split(":")[0]
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", fallback_host):
                host = fallback_host
            else:
                raise

        parts = host.split(".")

        is_ipv4 = re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host) is not None
        is_bare_host = host in ("localhost", "127.0.0.1") or is_ipv4 or len(parts) == 1

        if is_bare_host:
            org = None
        else:
            slug = parts[0]
            try:
                org = Organization.objects.get(slug=slug, is_active=True)
            except Organization.DoesNotExist:
                return JsonResponse({"detail": "Organization not found"}, status=404)

        request.org = org
        org_token = current_org.set(org)
        req_token = in_request_context.set(True)
        try:
            response = self.get_response(request)
        finally:
            current_org.reset(org_token)
            in_request_context.reset(req_token)

        return response