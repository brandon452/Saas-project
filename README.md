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
- Organization is resolved from request host subdomain in Django middleware.
- Middleware sets `request.org` and stores org in a thread-safe `contextvar`.
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
- Frontend: Vercel
- Backend: Render (use `gunicorn config.wsgi:application`)
- Database: Supabase (`DB_SSL_REQUIRE=true`)

## Production CORS
Update `CORS_ALLOWED_ORIGIN_REGEXES` in `apps/api/config/settings/prod.py` to your domain.
