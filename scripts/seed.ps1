param(
    [switch]$ResetDb,
    [string]$PostgresAdminUser = "postgres",
    [string]$PostgresAdminPassword = "admin",
    [string]$DbHost = "127.0.0.1",
    [string]$DbName = "inventory_main",
    [string]$DbUser = "inventory_user",
    [string]$DbPassword = "admin",
    [string]$SuperuserUsername = "admin",
    [string]$SuperuserEmail = "admin@example.com",
    [string]$SuperuserPassword = "admin123!"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

Write-Host "Seeding project from: $repoRoot"

if ($ResetDb) {
    Write-Host "Resetting database '$DbName'..."
    $env:PGPASSWORD = $PostgresAdminPassword
    psql -U $PostgresAdminUser -h $DbHost -d postgres -w -c "DROP DATABASE IF EXISTS $DbName;"
    $roleExists = psql -U $PostgresAdminUser -h $DbHost -d postgres -w -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DbUser'"
    if ($roleExists -eq "1") {
        psql -U $PostgresAdminUser -h $DbHost -d postgres -w -c "ALTER ROLE $DbUser LOGIN PASSWORD '$DbPassword';"
    } else {
        psql -U $PostgresAdminUser -h $DbHost -d postgres -w -c "CREATE ROLE $DbUser LOGIN PASSWORD '$DbPassword';"
    }
    psql -U $PostgresAdminUser -h $DbHost -d postgres -w -c "CREATE DATABASE $DbName OWNER $DbUser;"
    psql -U $PostgresAdminUser -h $DbHost -d postgres -w -c "GRANT ALL PRIVILEGES ON DATABASE $DbName TO $DbUser;"
}

Write-Host "Running migrations..."
npm.cmd run api:migrate

Write-Host "Creating superuser if needed..."
$env:DJANGO_SUPERUSER_USERNAME = $SuperuserUsername
$env:DJANGO_SUPERUSER_EMAIL = $SuperuserEmail
$env:DJANGO_SUPERUSER_PASSWORD = $SuperuserPassword
apps\api\.venv\Scripts\python.exe apps\api\manage.py createsuperuser --noinput 2>$null

$seedScript = @'
from django.contrib.auth import get_user_model
from tenancy.models import Organization, OrganizationMember
from branches.models import Branch
from inventory.models import Item, StockOnHand, StockLedger

User = get_user_model()

acme, _ = Organization.objects.get_or_create(slug="acme", defaults={"name": "Acme"})
globex, _ = Organization.objects.get_or_create(slug="globex", defaults={"name": "Globex"})

acme_user, _ = User.objects.get_or_create(username="acme_user", defaults={"email": "acme@example.com"})
acme_user.set_password("Passw0rd!")
acme_user.save()

globex_user, _ = User.objects.get_or_create(username="globex_user", defaults={"email": "globex@example.com"})
globex_user.set_password("Passw0rd!")
globex_user.save()

OrganizationMember.objects.update_or_create(
    user=acme_user,
    organization=acme,
    defaults={"role": "ADMIN", "is_active": True},
)
OrganizationMember.objects.update_or_create(
    user=globex_user,
    organization=globex,
    defaults={"role": "ADMIN", "is_active": True},
)

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

acme_item, _ = Item.objects.for_org(acme).update_or_create(
    organization=acme,
    sku="ACME-001",
    defaults={"name": "Acme Item", "is_active": True},
)
globex_item, _ = Item.objects.for_org(globex).update_or_create(
    organization=globex,
    sku="GLOBEX-001",
    defaults={"name": "Globex Item", "is_active": True},
)

StockLedger.objects.for_org(acme).filter(branch=acme_branch, item=acme_item).delete()
StockOnHand.objects.for_org(acme).filter(branch=acme_branch, item=acme_item).delete()
StockLedger.objects.for_org(globex).filter(branch=globex_branch, item=globex_item).delete()
StockOnHand.objects.for_org(globex).filter(branch=globex_branch, item=globex_item).delete()

print("Seed complete")
print("acme branch:", acme_branch.id)
print("globex branch:", globex_branch.id)
'@

Write-Host "Seeding demo data..."
apps\api\.venv\Scripts\python.exe apps\api\manage.py shell -c $seedScript

Write-Host "Done."
Write-Host "Run app with: npm run dev"
