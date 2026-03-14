from django.contrib import admin

from .models import Organization, OrganizationMember, ParentCompanyMember

admin.site.register(Organization)
admin.site.register(OrganizationMember)
admin.site.register(ParentCompanyMember)
