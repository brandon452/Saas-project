# Seeding Guide

## Purpose
Use this file to quickly reset and seed local demo data in PostgreSQL for this project.

## One Command Option
From repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\seed.ps1
```

With full DB reset:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\seed.ps1 -ResetDb
```

## Defaults Used
From `apps/api/.env`:
- DB: `inventory_main`
- DB user: `inventory_user`
- DB password: `admin`

From local setup:
- Postgres superuser: `postgres`
- Postgres superuser password: `admin`

## 1. Reset Database (Optional)
This drops and recreates `inventory_main`.

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

## 3. Create Superuser
```powershell
$env:DJANGO_SUPERUSER_USERNAME='admin'
$env:DJANGO_SUPERUSER_EMAIL='admin@example.com'
$env:DJANGO_SUPERUSER_PASSWORD='admin123!'
apps\api\.venv\Scripts\python.exe apps\api\manage.py createsuperuser --noinput
```

If it already exists, Django will report that and continue.

## 4. Seed Demo Users, Orgs, Branches, Items
```powershell
apps\api\.venv\Scripts\python.exe apps\api\manage.py shell -c @'
from django.contrib.auth import get_user_model
from tenancy.models import Organization, OrganizationMember
from branches.models import Branch
from inventory.models import Item, StockOnHand, StockLedger

User = get_user_model()

# Organizations
acme, _ = Organization.objects.get_or_create(slug="acme", defaults={"name": "Acme"})
globex, _ = Organization.objects.get_or_create(slug="globex", defaults={"name": "Globex"})

# Users
acme_user, _ = User.objects.get_or_create(username="acme_user", defaults={"email": "acme@example.com"})
acme_user.set_password("Passw0rd!")
acme_user.save()

globex_user, _ = User.objects.get_or_create(username="globex_user", defaults={"email": "globex@example.com"})
globex_user.set_password("Passw0rd!")
globex_user.save()

# Memberships
OrganizationMember.objects.update_or_create(
    user=acme_user, organization=acme, defaults={"role": "ADMIN", "is_active": True}
)
OrganizationMember.objects.update_or_create(
    user=globex_user, organization=globex, defaults={"role": "ADMIN", "is_active": True}
)

# Branches
acme_branch, _ = Branch.objects.for_org(acme).get_or_create(
    organization=acme, code="ACME-MAIN", defaults={"name": "Acme Main"}
)
globex_branch, _ = Branch.objects.for_org(globex).get_or_create(
    organization=globex, code="GLOBEX-MAIN", defaults={"name": "Globex Main"}
)

# Items
acme_item, _ = Item.objects.for_org(acme).update_or_create(
    organization=acme, sku="ACME-001", defaults={"name": "Acme Item", "is_active": True}
)
globex_item, _ = Item.objects.for_org(globex).update_or_create(
    organization=globex, sku="GLOBEX-001", defaults={"name": "Globex Item", "is_active": True}
)

# Reset stock rows for deterministic demos
StockLedger.objects.for_org(acme).filter(branch=acme_branch, item=acme_item).delete()
StockOnHand.objects.for_org(acme).filter(branch=acme_branch, item=acme_item).delete()
StockLedger.objects.for_org(globex).filter(branch=globex_branch, item=globex_item).delete()
StockOnHand.objects.for_org(globex).filter(branch=globex_branch, item=globex_item).delete()

print("Seed complete")
print("acme branch:", acme_branch.id)
print("globex branch:", globex_branch.id)
'@
```

## 5. Hosts File
Ensure `C:\Windows\System32\drivers\etc\hosts` includes:

```text
127.0.0.1 acme.localhost
127.0.0.1 globex.localhost
```

## 6. Start App
Before starting the web app, make sure the browser-facing API base uses `localhost`:

```powershell
Set-Content apps\web\.env.local "NEXT_PUBLIC_API_URL=http://localhost:8000"
```

```powershell
npm run dev
```

## 7. Quick Validation
```powershell
Invoke-WebRequest http://localhost:8000/api/health/ -Headers @{ Host = "localhost:8000" } | Select-Object -Expand Content
Invoke-WebRequest http://localhost:8000/api/health/ -Headers @{ Host = "acme.localhost:8000" } | Select-Object -Expand Content
```

Expected:
- localhost -> `organization: null`
- acme subdomain -> `organization: "acme"`

## 8. Local Login Note
If login succeeds and then immediately bounces back to `/login`, the usual cause is a host mismatch between `localhost` and `127.0.0.1`.

Use:

```text
Frontend: http://localhost:3000
API:      http://localhost:8000
```

Do not set `NEXT_PUBLIC_API_URL` to `http://127.0.0.1:8000` for browser-based local dev.
