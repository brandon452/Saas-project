from django.db.models import Manager, QuerySet

from .context import current_org, in_request_context


class TenantQuerySet(QuerySet):
    def for_org(self, org):
        return self.filter(organization=org)


class TenantManager(Manager):
    def get_queryset(self):
        org = current_org.get()
        in_request = in_request_context.get()

        if in_request and org is None:
            raise RuntimeError(
                "Organization context missing during request. "
                "Ensure TenantMiddleware is installed and running."
            )

        if org is not None:
            return TenantQuerySet(self.model, using=self._db).filter(organization=org)

        return TenantQuerySet(self.model, using=self._db)

    def for_org(self, org):
        return TenantQuerySet(self.model, using=self._db).filter(organization=org)


class OrganizationMemberQuerySet(QuerySet):
    def for_org(self, org):
        return self.filter(organization=org)


class OrganizationMemberManager(Manager):
    def get_queryset(self):
        return OrganizationMemberQuerySet(self.model, using=self._db)

    def for_org(self, org):
        return self.get_queryset().for_org(org)
