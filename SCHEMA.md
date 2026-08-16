# SQCS Data Model

`users` — identity, hashed password, role, activation status and login timestamps.

`projects` — project metadata plus a JSON checklist document. JSON is used here because the original SQCS checklist is hierarchical and templates can evolve without destructive schema rewrites.

`checklist_templates` — named/versionable JSON checklist structures used to initialize and edit project reviews.

`documents` — file metadata plus binary content for a simple persistent deployment. For high-volume files, move the binary payload to object storage and keep metadata here.

`audit_logs` — append-only-style activity records for authentication, project, checklist, document, template and administration operations.
