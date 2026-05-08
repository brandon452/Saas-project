# Testing Guide (Current Architecture)

## Prerequisites
- Node dependencies installed: `npm install`
- Python venv + backend dependencies installed
- PostgreSQL running with values from `apps/api/.env`
- Demo data seeded using [SEEDING.md](c:/Users/Admin/Documents/Saas%20project/SEEDING.md)

## 1. Run the App
From repo root:

```powershell
npm run dev
```

Or separately:

```powershell
npm run dev:web
npm run dev:api
```

## 2. Smoke Checks
```powershell
Invoke-WebRequest http://localhost:8000/api/health/ | Select-Object -Expand Content
Invoke-WebRequest http://localhost:8000/api/schema/ | Select-Object -Expand StatusCode
Invoke-WebRequest http://localhost:8000/api/docs/ | Select-Object -Expand StatusCode
```

Expected:
- health: `status` is present, `db` is `ok`
- schema/docs: `200`

## 3. Get IDs Needed for Org-Scoped Routes
Use Django shell once to fetch seeded IDs:

```powershell
apps\api\.venv\Scripts\python.exe apps\api\manage.py shell -c @'
from tenancy.models import Organization
from branches.models import Branch
from inventory.models import OrgItem

acme = Organization.objects.get(slug="acme")
globex = Organization.objects.get(slug="globex")

acme_branch = Branch.objects.for_org(acme).get(code="ACME-MAIN")
globex_branch = Branch.objects.for_org(globex).get(code="GLOBEX-MAIN")

acme_item = OrgItem.objects.for_org(acme).get(master_item__sku="ACME-001")

print("ACME_ORG_ID=", acme.id, sep="")
print("GLOBEX_ORG_ID=", globex.id, sep="")
print("ACME_BRANCH_ID=", acme_branch.id, sep="")
print("GLOBEX_BRANCH_ID=", globex_branch.id, sep="")
print("ACME_ITEM_ID=", acme_item.id, sep="")
'@
```

Set those values in your shell:

```powershell
$ACME_ORG_ID = "<paste>"
$GLOBEX_ORG_ID = "<paste>"
$ACME_BRANCH_ID = "<paste>"
$GLOBEX_BRANCH_ID = "<paste>"
$ACME_ITEM_ID = "<paste>"
```

## 4. Get JWT Tokens
```powershell
$acmeTokenResp = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/api/token/" `
  -ContentType "application/json" `
  -Body '{"username":"acme_admin","password":"Passw0rd!"}'

$globexTokenResp = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/api/token/" `
  -ContentType "application/json" `
  -Body '{"username":"globex_admin","password":"Passw0rd!"}'

$acmeToken = $acmeTokenResp.access
$globexToken = $globexTokenResp.access
```

## 5. Tenancy and Membership Checks
Acme user on Acme org (`200`):

```powershell
Invoke-WebRequest `
  -Uri "http://localhost:8000/api/orgs/$ACME_ORG_ID/inventory/items/" `
  -Headers @{ Authorization = "Bearer $acmeToken" } |
  Select-Object -Expand StatusCode
```

Acme user on Globex org (`403`):

```powershell
Invoke-WebRequest `
  -Uri "http://localhost:8000/api/orgs/$GLOBEX_ORG_ID/inventory/items/" `
  -Headers @{ Authorization = "Bearer $acmeToken" } `
  -ErrorAction SilentlyContinue |
  Select-Object -Expand StatusCode
```

## 6. Branch Validation Checks (Stock Movement)
Missing branch header (`400`):

```powershell
Invoke-WebRequest `
  -Method POST `
  -Uri "http://localhost:8000/api/orgs/$ACME_ORG_ID/inventory/movements/" `
  -Headers @{ Authorization = "Bearer $acmeToken" } `
  -ContentType "application/json" `
  -Body "{""item"":""$ACME_ITEM_ID"",""quantity"":""1.0000"",""movement_type"":""RECEIPT"",""unit_cost"":""1.5000""}" `
  -ErrorAction SilentlyContinue |
  Select-Object -Expand StatusCode
```

Unknown branch UUID (`400`):

```powershell
Invoke-WebRequest `
  -Method POST `
  -Uri "http://localhost:8000/api/orgs/$ACME_ORG_ID/inventory/movements/" `
  -Headers @{ Authorization = "Bearer $acmeToken"; "X-BRANCH-ID" = "11111111-1111-1111-1111-111111111111" } `
  -ContentType "application/json" `
  -Body "{""item"":""$ACME_ITEM_ID"",""quantity"":""1.0000"",""movement_type"":""RECEIPT"",""unit_cost"":""1.5000""}" `
  -ErrorAction SilentlyContinue |
  Select-Object -Expand StatusCode
```

Branch from different org (`403`):

```powershell
Invoke-WebRequest `
  -Method POST `
  -Uri "http://localhost:8000/api/orgs/$ACME_ORG_ID/inventory/movements/" `
  -Headers @{ Authorization = "Bearer $acmeToken"; "X-BRANCH-ID" = "$GLOBEX_BRANCH_ID" } `
  -ContentType "application/json" `
  -Body "{""item"":""$ACME_ITEM_ID"",""quantity"":""1.0000"",""movement_type"":""RECEIPT"",""unit_cost"":""1.5000""}" `
  -ErrorAction SilentlyContinue |
  Select-Object -Expand StatusCode
```

Valid branch (`201`):

```powershell
Invoke-WebRequest `
  -Method POST `
  -Uri "http://localhost:8000/api/orgs/$ACME_ORG_ID/inventory/movements/" `
  -Headers @{ Authorization = "Bearer $acmeToken"; "X-BRANCH-ID" = "$ACME_BRANCH_ID" } `
  -ContentType "application/json" `
  -Body "{""item"":""$ACME_ITEM_ID"",""quantity"":""1.0000"",""movement_type"":""RECEIPT"",""unit_cost"":""1.5000""}" |
  Select-Object -Expand StatusCode
```

## 7. Idempotent Retry Example (`201` then `200`)
```powershell
$idemKey = "acme-receipt-001"
$body = @{
  item = "$ACME_ITEM_ID"
  quantity = "2.0000"
  movement_type = "RECEIPT"
  unit_cost = "2.2500"
  reference_type = "SEED_TEST"
  reference_id = "seed-test-001"
  reason = "Idempotency verification"
  idempotency_key = $idemKey
} | ConvertTo-Json

$first = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/api/orgs/$ACME_ORG_ID/inventory/movements/" `
  -Headers @{ Authorization = "Bearer $acmeToken"; "X-BRANCH-ID" = "$ACME_BRANCH_ID" } `
  -ContentType "application/json" `
  -Body $body `
  -StatusCodeVariable firstStatus

$second = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/api/orgs/$ACME_ORG_ID/inventory/movements/" `
  -Headers @{ Authorization = "Bearer $acmeToken"; "X-BRANCH-ID" = "$ACME_BRANCH_ID" } `
  -ContentType "application/json" `
  -Body $body `
  -StatusCodeVariable secondStatus

"firstStatus=$firstStatus secondStatus=$secondStatus firstId=$($first.id) secondId=$($second.id)"
```

Expected:
- `firstStatus = 201`
- `secondStatus = 200`
- `first.id == second.id`

## 8. CORS Check (Optional)
```powershell
(Invoke-WebRequest "http://localhost:8000/api/health/" -Headers @{ Origin = "http://localhost:3000" }).Headers["Access-Control-Allow-Origin"]
```

## Notes
- Tenancy is URL-based (`/api/orgs/{org_id}/...`), not host/subdomain based.
- Stock writes must go through `POST /api/orgs/{org_id}/inventory/movements/`.
- For browser/local auth stability, use consistent hostnames (`localhost` for both web and API).
