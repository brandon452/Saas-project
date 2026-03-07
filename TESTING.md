# Testing Guide

## Prerequisites
- Node dependencies installed: `npm install`
- Python venv and backend deps installed
- PostgreSQL running with values from `apps/api/.env`
- Hosts file includes tenant domains, for example:
  - `127.0.0.1 acme.localhost`
  - `127.0.0.1 globex.localhost`

## Run the App
From repo root:

```powershell
npm run dev
```

Or separately:

```powershell
npm run dev:web
npm run dev:api
```

## Smoke Checks
```powershell
Invoke-WebRequest http://localhost:8000/api/health/ -Headers @{ Host = "localhost:8000" } | Select-Object -Expand Content
Invoke-WebRequest http://localhost:8000/api/health/ -Headers @{ Host = "acme.localhost:8000" } | Select-Object -Expand Content
Invoke-WebRequest http://localhost:8000/api/schema/ -Headers @{ Host = "localhost:8000" } | Select-Object -Expand StatusCode
Invoke-WebRequest http://localhost:8000/api/docs/ -Headers @{ Host = "localhost:8000" } | Select-Object -Expand StatusCode
```

Expected:
- localhost health: organization is `null`
- acme health: organization is `"acme"`
- schema/docs: `200`

## Get JWT Tokens
```powershell
$acmeTokenResp = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/api/token/" `
  -Headers @{ Host = "acme.localhost:8000" } `
  -ContentType "application/json" `
  -Body '{"username":"acme_user","password":"Passw0rd!"}'

$globexTokenResp = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/api/token/" `
  -Headers @{ Host = "globex.localhost:8000" } `
  -ContentType "application/json" `
  -Body '{"username":"globex_user","password":"Passw0rd!"}'

$acmeToken = $acmeTokenResp.access
$globexToken = $globexTokenResp.access
```

## Tenancy and Membership Checks
```powershell
# acme user on acme org: 200
Invoke-WebRequest `
  -Uri "http://localhost:8000/api/items/" `
  -Headers @{ Host = "acme.localhost:8000"; Authorization = "Bearer $acmeToken" } |
  Select-Object -Expand Content

# acme user on globex org: 403
Invoke-WebRequest `
  -Uri "http://localhost:8000/api/items/" `
  -Headers @{ Host = "globex.localhost:8000"; Authorization = "Bearer $acmeToken" } `
  -ErrorAction SilentlyContinue
```

## Branch Validation Checks
First get branch IDs:

```powershell
$acmeBranches = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/branches/" `
  -Headers @{ Host = "acme.localhost:8000"; Authorization = "Bearer $acmeToken" }

$globexBranches = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/branches/" `
  -Headers @{ Host = "globex.localhost:8000"; Authorization = "Bearer $globexToken" }

$acmeBranchId = $acmeBranches.results[0].id
$globexBranchId = $globexBranches.results[0].id

$acmeItems = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/items/" `
  -Headers @{ Host = "acme.localhost:8000"; Authorization = "Bearer $acmeToken" }

$acmeItemId = $acmeItems.results[0].id
```

Missing branch header (`400`):

```powershell
Invoke-WebRequest `
  -Method POST `
  -Uri "http://localhost:8000/api/inventory/movements/" `
  -Headers @{ Host = "acme.localhost:8000"; Authorization = "Bearer $acmeToken" } `
  -ContentType "application/json" `
  -Body "{""item"":""$acmeItemId"",""quantity"":""1.0000"",""movement_type"":""RECEIPT""}" `
  -ErrorAction SilentlyContinue
```

Unknown branch UUID (`400`):

```powershell
Invoke-WebRequest `
  -Method POST `
  -Uri "http://localhost:8000/api/inventory/movements/" `
  -Headers @{ Host = "acme.localhost:8000"; Authorization = "Bearer $acmeToken"; "X-BRANCH-ID" = "11111111-1111-1111-1111-111111111111" } `
  -ContentType "application/json" `
  -Body "{""item"":""$acmeItemId"",""quantity"":""1.0000"",""movement_type"":""RECEIPT""}" `
  -ErrorAction SilentlyContinue
```

Branch from different org (`403`):

```powershell
Invoke-WebRequest `
  -Method POST `
  -Uri "http://localhost:8000/api/inventory/movements/" `
  -Headers @{ Host = "acme.localhost:8000"; Authorization = "Bearer $acmeToken"; "X-BRANCH-ID" = "$globexBranchId" } `
  -ContentType "application/json" `
  -Body "{""item"":""$acmeItemId"",""quantity"":""1.0000"",""movement_type"":""RECEIPT""}" `
  -ErrorAction SilentlyContinue
```

Valid branch (`201`):

```powershell
Invoke-WebRequest `
  -Method POST `
  -Uri "http://localhost:8000/api/inventory/movements/" `
  -Headers @{ Host = "acme.localhost:8000"; Authorization = "Bearer $acmeToken"; "X-BRANCH-ID" = "$acmeBranchId" } `
  -ContentType "application/json" `
  -Body "{""item"":""$acmeItemId"",""quantity"":""1.0000"",""movement_type"":""RECEIPT""}"
```

## Idempotent Retry Example (`201` then `200`)
```powershell
$idemKey = "acme-receipt-001"
$body = @{
  item = "$acmeItemId"
  quantity = "2.0000"
  movement_type = "RECEIPT"
  reference_type = "PURCHASE_RECEIPT"
  reference_id = "po_2026_03_06_001"
  reason = "Initial receipt"
  idempotency_key = $idemKey
} | ConvertTo-Json

$first = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/api/inventory/movements/" `
  -Headers @{ Host = "acme.localhost:8000"; Authorization = "Bearer $acmeToken"; "X-BRANCH-ID" = "$acmeBranchId" } `
  -ContentType "application/json" `
  -Body $body `
  -StatusCodeVariable firstStatus

$second = Invoke-RestMethod `
  -Method POST `
  -Uri "http://localhost:8000/api/inventory/movements/" `
  -Headers @{ Host = "acme.localhost:8000"; Authorization = "Bearer $acmeToken"; "X-BRANCH-ID" = "$acmeBranchId" } `
  -ContentType "application/json" `
  -Body $body `
  -StatusCodeVariable secondStatus

"firstStatus=$firstStatus secondStatus=$secondStatus firstId=$($first.id) secondId=$($second.id)"
```

Expected:
- `firstStatus = 201`
- `secondStatus = 200`
- `first.id == second.id` (deduplicated, no second stock apply)

## CORS Checks
```powershell
(Invoke-WebRequest "http://localhost:8000/api/health/" -Headers @{ Host = "acme.localhost:8000"; Origin = "http://acme.localhost:3000" }).Headers["Access-Control-Allow-Origin"]
(Invoke-WebRequest "http://localhost:8000/api/health/" -Headers @{ Host = "localhost:8000"; Origin = "http://localhost:3000" }).Headers["Access-Control-Allow-Origin"]
```

## JWT Org Claim Check
```powershell
$payload = $acmeToken.Split(".")[1].Replace("-", "+").Replace("_", "/")
switch ($payload.Length % 4) { 2 { $payload += "==" } 3 { $payload += "=" } }
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payload))
```

Expected: payload contains user info and token fields, but no organization field.

## Add a New Organization
```powershell
apps\api\.venv\Scripts\python.exe apps\api\manage.py shell
```

Then in shell:

```python
from django.contrib.auth import get_user_model
from tenancy.models import Organization, OrganizationMember
from branches.models import Branch

User = get_user_model()

org, _ = Organization.objects.get_or_create(slug="newco", defaults={"name": "NewCo"})
Branch.objects.for_org(org).get_or_create(
    organization=org,
    code="NEWCO-MAIN",
    defaults={"name": "NewCo Main"},
)

user = User.objects.get(username="acme_user")
OrganizationMember.objects.update_or_create(
    user=user,
    organization=org,
    defaults={"role": "ADMIN", "is_active": True},
)
```

Add hosts entry:

```text
127.0.0.1 newco.localhost
```

Now test with `Host: newco.localhost:8000`.

## Notes
- Tenant resolution is host-based only.
- Passing org in request body/JWT/custom headers is ignored by tenancy resolution.
- Stock writes must go through `/api/inventory/movements/`.
