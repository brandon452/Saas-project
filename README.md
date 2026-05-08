# Multi-Tenant Inventory System

## Requirements
- Node 20 (see `.nvmrc`)
- Python 3.14
- PostgreSQL local instance

## PostgreSQL Setup
```sql
CREATE DATABASE inventory;
CREATE USER inventory_app WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE inventory TO inventory_app;
```

## Python Virtual Environment
```powershell
# Create
python -m venv apps/api/.venv

# PowerShell
apps/api/.venv/Scripts/Activate.ps1

# CMD
apps/api/.venv/Scripts/activate.bat
```

## Install Dependencies
```powershell
pip install -r apps/api/requirements.txt
npm install
```

## Environment
Create `apps/api/.env` from `infra/.env.example` and set DB credentials.

## Run Migrations
```powershell
npm run api:migrate
```

## Create Superuser
```powershell
npm run api:createsuperuser
```

## Initial Production Run
For the first live startup flow, including `/setup` and adding parent companies later, see:

```text
docs/initial-run.md
```

## Start Dev Servers
```powershell
npm run dev
```

## Hosts Entries (Windows)
Add to `C:\Windows\System32\drivers\etc\hosts`:

```text
127.0.0.1 acme.localhost
127.0.0.1 globex.localhost
```

## Tenancy Model
- Organization is resolved from `/api/orgs/{org_id}/...` URL kwargs in org-scoped views/mixins.
- `X-BRANCH-ID` is parsed by middleware and attached as `request.branch` when possible.
- Branch/org/role enforcement happens in scoped view logic (for example `OrgScopedViewSetMixin` + `BranchScopedMixin`), not at header-parse time.
- All API viewsets/services must call `.for_org(request.org)` explicitly.
- Manager auto-scope is defense in depth only.
- If a tenant queryset is accessed during request handling without org context, runtime error is raised.
- Bare hosts/IP addresses set `request.org = None`; only non-tenant endpoints should be called.
- Django admin is intentionally unscoped and superuser-only.

## Stock Movement Audit + Idempotency
- Stock writes must always go through `record_stock_movement()` in `apps/api/inventory/services.py`.
- Direct writes to `StockOnHand` or `StockLedger` from ViewSets are prohibited.
- Movement create endpoint: `POST /api/inventory/movements/`.
- `reference_type` + `reference_id` are audit links back to source business documents. They are not duplicate prevention.
- `reason` is a human-readable explanation (required by convention for manual adjustments).
- `performed_by` is always set server-side from `request.user` and never trusted from client input.
- `occurred_at` is when the movement happened in real-world time. If omitted, it defaults to request-time (`timezone.now()`). It is distinct from `created_at` (DB insert time).
- `idempotency_key` prevents double-processing of retries and is scoped per organization.
- The database partial unique constraint on `(organization, idempotency_key)` (non-null keys only) is the authoritative guarantee for deduplication.
- One `idempotency_key` represents exactly one stock movement. Clients must generate a fresh key for each distinct write.

## Deployment Targets
- Frontend: Vercel (root directory: `apps/web`)
- Backend: Railway (reads `railway.toml` at repo root)
- Database: Supabase (Session pooler, `DB_SSL_REQUIRE=true`)
- Redis: Upstash (copy `REDIS_URL` from Upstash console)

## Production Environment Variables
See `infra/.env.example` for the full list of required variables.
Set them in Railway (backend) and Vercel (frontend) — do not commit real values.

## Production CORS
Set `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` as environment variables in Railway.
No code changes needed — `prod.py` reads them automatically.
