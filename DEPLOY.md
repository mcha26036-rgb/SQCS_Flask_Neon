# Production deployment: Neon + Vercel

## 1. Create Neon database

Create a Postgres database in Neon and copy its connection string. Keep SSL enabled.

Set:

`DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`

## 2. Prepare production secrets

Generate a random Flask secret and choose a strong administrator password.

Set:

```text
SECRET_KEY=<long-random-value>
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<strong-password>
ADMIN_NAME=System Administrator
ADMIN_EMAIL=<admin-email>
SESSION_COOKIE_SECURE=true
MAX_CONTENT_MB=12
```

## 3. Deploy to Vercel

Import this repository/project into Vercel. The included `vercel.json` points Vercel to `api/index.py`, which exposes the Flask WSGI application.

Add the environment variables above to the Production environment before or during the first deployment.

## 4. First login

Open the deployment URL and sign in with the admin credentials from the environment variables. The first application startup creates the database tables, seeds the SQCR/legacy templates and creates the administrator if it is not already present.

## 5. Verify

Open `/health`. A healthy deployment returns JSON similar to:

```json
{"status":"ok","database":"connected"}
```

Then create a test project, answer several checklist items, reload the page, and confirm that the saved results remain present. Generate the report and confirm that Print / Save PDF works from the browser.

## 6. Scaling documents

This implementation keeps document binaries in the `documents` table for a simple self-contained deployment. For a large evidence repository, move file bytes to object storage and keep metadata/audit records in Neon.
