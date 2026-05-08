# Seeding Guide (Current Architecture)

## Purpose
Seed local demo data for the current multi-tenant model:
- `ParentCompany`
- `Organization`
- `Branch`
- `MasterItem` -> `OrgItem` -> `BranchItem`
- Stock via `record_stock_movement()`

This guide matches the current URL-based tenancy (`/api/orgs/{org_id}/...`).

## Prerequisites
- PostgreSQL running locally
- `apps/api/.venv` created
- `apps/api/.env` configured

Install dependencies if needed:

```powershell
pip install -r apps/api/requirements.txt
npm install
```

## 1. Reset Database (Optional)
Use this only if you want a clean local DB.

```powershell
$env:PGPASSWORD='admin'
psql -U postgres -h 127.0.0.1 -d postgres -w -c "DROP DATABASE IF EXISTS inventory_main;"
psql -U postgres -h 127.0.0.1 -d postgres -w -c "CREATE DATABASE inventory_main OWNER inventory_user;"
psql -U postgres -h 127.0.0.1 -d postgres -w -c "GRANT ALL PRIVILEGES ON DATABASE inventory_main TO inventory_user;"
```

## 2. Run Migrations
```powershell
npm run api:migrate
```

## 3. Create Superuser (Optional)
```powershell
$env:DJANGO_SUPERUSER_USERNAME='admin'
$env:DJANGO_SUPERUSER_EMAIL='admin@example.com'
$env:DJANGO_SUPERUSER_PASSWORD='admin123!'
apps\api\.venv\Scripts\python.exe apps\api\manage.py createsuperuser --noinput
```

## 4. Seed Demo Data
Run this from repo root:

```powershell
apps\api\.venv\Scripts\python.exe apps\api\manage.py shell -c @'
from decimal import Decimal
from django.contrib.auth import get_user_model
from tenancy.models import ParentCompany, Organization, OrganizationMember
from branches.models import Branch
from inventory.models import MasterItem, OrgItem, BranchItem, StockOnHand, StockLedger
from inventory.services import record_stock_movement

User = get_user_model()

# Parent companies
parent_a, _ = ParentCompany.objects.get_or_create(
    slug="parent-a",
    defaults={"name": "Parent A", "is_active": True},
)
parent_b, _ = ParentCompany.objects.get_or_create(
    slug="parent-b",
    defaults={"name": "Parent B", "is_active": True},
)

# Organizations
acme, _ = Organization.objects.get_or_create(
    slug="acme",
    defaults={"name": "Acme", "parent_company": parent_a, "is_active": True},
)
globex, _ = Organization.objects.get_or_create(
    slug="globex",
    defaults={"name": "Globex", "parent_company": parent_a, "is_active": True},
)
initech, _ = Organization.objects.get_or_create(
    slug="initech",
    defaults={"name": "Initech", "parent_company": parent_b, "is_active": True},
)

# Users
acme_admin, _ = User.objects.get_or_create(username="acme_admin", defaults={"email": "acme@example.com"})
acme_admin.set_password("Passw0rd!")
acme_admin.save(update_fields=["password"])

globex_admin, _ = User.objects.get_or_create(username="globex_admin", defaults={"email": "globex@example.com"})
globex_admin.set_password("Passw0rd!")
globex_admin.save(update_fields=["password"])

acme_staff, _ = User.objects.get_or_create(username="acme_staff", defaults={"email": "acme_staff@example.com"})
acme_staff.set_password("Passw0rd!")
acme_staff.save(update_fields=["password"])

# Branches
acme_branch, _ = Branch.objects.for_org(acme).get_or_create(
    organization=acme,
    code="ACME-MAIN",
    defaults={"name": "Acme Main"},
)
globex_branch, _ = Branch.objects.for_org(globex).get_or_create(
    organization=globex,
    code="GLOBEX-MAIN",
    defaults={"name": "Globex Main"},
)
initech_branch, _ = Branch.objects.for_org(initech).get_or_create(
    organization=initech,
    code="INITECH-MAIN",
    defaults={"name": "Initech Main"},
)

# Memberships
OrganizationMember.objects.update_or_create(
    user=acme_admin,
    organization=acme,
    defaults={"role": OrganizationMember.ROLE_ADMIN, "is_active": True, "assigned_branch": None},
)
OrganizationMember.objects.update_or_create(
    user=globex_admin,
    organization=globex,
    defaults={"role": OrganizationMember.ROLE_ADMIN, "is_active": True, "assigned_branch": None},
)
OrganizationMember.objects.update_or_create(
    user=acme_staff,
    organization=acme,
    defaults={"role": OrganizationMember.ROLE_STAFF, "is_active": True, "assigned_branch": acme_branch},
)

# Master + org + branch items
master_acme, _ = MasterItem.objects.get_or_create(
    parent_company=parent_a,
    sku="ACME-001",
    defaults={"name": "Acme Demo Item", "is_active": True},
)
master_globex, _ = MasterItem.objects.get_or_create(
    parent_company=parent_a,
    sku="GLOBEX-001",
    defaults={"name": "Globex Demo Item", "is_active": True},
)
master_initech, _ = MasterItem.objects.get_or_create(
    parent_company=parent_b,
    sku="INITECH-001",
    defaults={"name": "Initech Demo Item", "is_active": True},
)

acme_org_item, _ = OrgItem.objects.for_org(acme).get_or_create(
    organization=acme,
    master_item=master_acme,
    defaults={"name": "Acme Item", "is_active": True},
)
globex_org_item, _ = OrgItem.objects.for_org(globex).get_or_create(
    organization=globex,
    master_item=master_globex,
    defaults={"name": "Globex Item", "is_active": True},
)
initech_org_item, _ = OrgItem.objects.for_org(initech).get_or_create(
    organization=initech,
    master_item=master_initech,
    defaults={"name": "Initech Item", "is_active": True},
)

BranchItem.objects.get_or_create(branch=acme_branch, org_item=acme_org_item, defaults={"is_active": True})
BranchItem.objects.get_or_create(branch=globex_branch, org_item=globex_org_item, defaults={"is_active": True})
BranchItem.objects.get_or_create(branch=initech_branch, org_item=initech_org_item, defaults={"is_active": True})

# Reset stock rows for deterministic seed
StockLedger.objects.for_org(acme).filter(branch=acme_branch, item=acme_org_item).delete()
StockOnHand.objects.for_org(acme).filter(branch=acme_branch, item=acme_org_item).delete()

# Seed opening stock using the canonical service
record_stock_movement(
    org=acme,
    branch=acme_branch,
    item=acme_org_item,
    quantity=Decimal("50.0000"),
    movement_type=StockLedger.MOVEMENT_RECEIPT,
    unit_cost=Decimal("2.5000"),
    reference_type="SEED",
    reference_id="ACME-OPENING",
    reason="Local demo seed",
    performed_by=acme_admin,
    idempotency_key="seed-acme-opening-v1",
)

print("Seed complete")
print(f"acme org id: {acme.id}")
print(f"acme branch id: {acme_branch.id}")
print(f"acme item id: {acme_org_item.id}")
print("users:")
print("  acme_admin / Passw0rd!")
print("  globex_admin / Passw0rd!")
print("  acme_staff / Passw0rd!")
'@
```

## 5. Start App
```powershell
npm run dev
```

## 6. Quick Validation
Health check:

```powershell
Invoke-WebRequest http://localhost:8000/api/health/ | Select-Object -Expand Content
```

Example org-scoped call (replace placeholders):

```powershell
Invoke-WebRequest "http://localhost:8000/api/orgs/<ORG_ID>/inventory/stock/" `
  -Headers @{ Authorization = "Bearer <ACCESS_TOKEN>"; "X-BRANCH-ID" = "<BRANCH_ID>" } `
  | Select-Object -Expand Content
```

## Notes
- Subdomain hosts entries are not required for tenancy in the current backend architecture.
- Use `localhost` consistently for browser/API local dev to avoid cookie/CSRF host mismatch issues.
