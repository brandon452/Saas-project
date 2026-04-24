from django.contrib import admin

from .models import Organization, OrganizationMember, ParentCompany, ParentCompanyMember

admin.site.register(ParentCompany)
admin.site.register(Organization)
admin.site.register(OrganizationMember)
admin.site.register(ParentCompanyMember)
