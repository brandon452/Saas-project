# Initial Production Run

This guide explains how to start a fresh live instance after deployment.

## 1. Deploy and Configure

Set the production environment variables for the backend, frontend, database, and Redis.

At minimum, confirm:

- Backend can reach the production Postgres database.
- Frontend `NEXT_PUBLIC_API_URL` points to the backend URL.
- `FRONTEND_URL` points to the frontend URL.
- CORS and CSRF trusted origins include the frontend URL.

## 2. Run Database Migrations

Run migrations once the backend has access to the production database:

```powershell
apps\api\.venv\Scripts\python.exe apps\api\manage.py migrate
```

This creates the schema, including:

- `ParentCompany`
- `ParentCompanyMember`
- `Organization`
- parent-company-scoped master items

## 3. Complete First-Run Setup

Open the setup page in a browser:

```text
https://your-frontend-domain.com/setup
```

This page is only usable when no active parent admin exists.

Enter:

- Parent company name
- Parent company slug
- First parent admin first name
- First parent admin last name
- First parent admin email
- First parent admin password

Submitting the form creates:

- The first `ParentCompany`
- The first parent admin user
- A `ParentCompanyMember` with role `PARENT_ADMIN`

The setup flow logs the new parent admin in automatically.

## 4. Create the First Organization

After logging in as the parent admin, create the first organization/company from the parent admin flow.

An organization represents an operating company, branch group, or tenant under the parent company.

After the organization exists, continue setup:

- Add branches.
- Add users.
- Add master items.
- Activate items for the organization.
- Add suppliers.
- Begin purchase orders, goods receipts, transfers, quick sales, and reports.

## 5. Add More Parent Companies Later

The `/setup` page is not used again after the first parent admin exists.

To add another parent company:

1. Log in as a Django superuser.
2. Go to:

```text
https://your-frontend-domain.com/operator/parent-companies
```

3. Create the new parent company and its first parent admin.
4. Send the returned password setup link to that parent admin.

## Access Model

```text
Django superuser
  -> manages parent companies from /operator/parent-companies

Parent company
  -> has parent admins and parent viewers
  -> owns organizations
  -> owns master items

Organization
  -> has branches
  -> has organization users
  -> has inventory, suppliers, orders, sales, reports
```

Parent admins can only see and manage organizations under their own parent company.

## Safety Notes

- `/setup` returns setup complete once an active parent admin exists.
- Additional parent companies require a Django superuser.
- Parent-company data is scoped in the backend; parent users cannot access another parent company's organizations.
- Keep the Django superuser account restricted to operators only.
