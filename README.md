# SQCS Platform — Flask + Neon + Vercel

A full web conversion of the original SQCS Streamlit platform into a professional Flask application with persistent PostgreSQL/Neon storage.

## Included functionality

- Secure login, sign-up, password hashing, roles and admin control
- Dashboard with project portfolio, compliance signals and activity/audit trail
- Project creation, editing, lifecycle status and assessment metadata
- Dynamic checklist templates seeded from the original SQCR and legacy JSON templates
- Checklist responses: Excellent, Need Review, Fail and N/A
- Persistent checklist feedback and browser autosave
- Section-level completion/compliance analytics
- Print-ready HTML report with "Print / Save PDF"
- JSON export for complete project assessments
- Controlled document library with upload, categorization, tagging, download and deletion
- Admin console for users, templates, projects and audit log
- Health endpoint for deployment monitoring
- Neon PostgreSQL persistence; local SQLite fallback for development
- Vercel Python/Flask entrypoint and deployment configuration

## Local run

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env  # macOS/Linux
python app.py
```

Open `http://127.0.0.1:5000`.

For local development, leaving `DATABASE_URL` empty uses `instance/sqcs.db`.

## Neon

Create a Neon Postgres database and put its connection string into `DATABASE_URL`. The application accepts either `postgresql://...` or `postgres://...` and adapts it to the Psycopg SQLAlchemy driver.

Example:

```text
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require
```

The app creates its tables on startup and seeds the included checklist templates and first admin account when the database is empty.

## Vercel

The Vercel entrypoint is `api/index.py` and `vercel.json` is already included.

Set these Environment Variables in the Vercel project:

- `DATABASE_URL`
- `SECRET_KEY`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `ADMIN_NAME`
- `ADMIN_EMAIL`
- `MAX_CONTENT_MB` (optional; defaults to 12)
- `SESSION_COOKIE_SECURE=true`

Then deploy the repository to Vercel.

## Security notes

- Do not keep the sample admin password in production.
- Use a long random `SECRET_KEY`.
- Keep Neon SSL enabled (`sslmode=require`).
- Restrict admin accounts to administrators only.
- Review the audit log regularly.
- For large document workloads, replace database BLOB storage with object storage (for example Vercel Blob) while keeping the `documents` metadata table in Neon.

## Migrating legacy projects

The original archive did not contain populated project folders, but an importer is included:

```bash
python scripts/import_legacy.py --source "C:\path\to\old\SQCS_Platform-main"
```

The importer preserves project metadata and checklist JSON. Documents should be migrated according to your storage policy.
