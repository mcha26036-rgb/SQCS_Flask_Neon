import io
import json
import csv
import secrets

from datetime import datetime, timezone
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    send_file,
    abort,
    current_app,
)

from markupsafe import escape
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db
from .models import (
    User,
    Project,
    ChecklistTemplate,
    Document,
    AuditLog,
)
from .services import *


bp = Blueprint("main", __name__)


# ============================================================
# USER / AUTHENTICATION HELPERS
# ============================================================

def current_user():
    """
    Return the currently authenticated user, or None.
    """
    uid = session.get("user_id")

    if not uid:
        return None

    try:
        return User.query.get(uid)
    except Exception:
        current_app.logger.exception("Failed to load current user")
        return None


def login_required(f):
    """
    Require an authenticated and active user.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()

        if not user or not user.active:
            session.clear()

            if request.path.startswith("/api/"):
                return jsonify(
                    ok=False,
                    error="Authentication required"
                ), 401

            flash(
                "Please sign in to continue.",
                "warning"
            )

            return redirect(
                url_for(
                    "main.login",
                    next=request.path
                )
            )

        return f(*args, **kwargs)

    return wrapper


def admin_required(f):
    """
    Require an authenticated administrator.
    """

    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()

        if not user or user.role != "admin":
            abort(403)

        return f(*args, **kwargs)

    return login_required(wrapper)


# ============================================================
# CSRF
# ============================================================

def csrf_ok():
    """
    Validate the current CSRF token.
    """

    token = session.get("csrf_token")

    provided = (
        request.form.get("_csrf")
        or request.headers.get("X-CSRF-Token")
    )

    return bool(
        token
        and provided
        and secrets.compare_digest(
            token,
            provided
        )
    )


def ensure_csrf():
    """
    Ensure every session has a CSRF token.
    """

    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["csrf_token"]


def base_context(**kwargs):
    """
    Common template context.
    """

    context = {
        "current_user": current_user(),
        "csrf_token": ensure_csrf(),
    }

    context.update(kwargs)

    return context


# ============================================================
# PROJECT HELPERS
# ============================================================

def project_or_404(pid):
    """
    Return project or abort with HTTP 404.
    """

    p = Project.query.get(pid)

    if not p:
        abort(404)

    return p


# ============================================================
# TEMPLATE GLOBALS
# ============================================================

@bp.context_processor
def inject_globals():
    return {
        "current_user": current_user(),
        "csrf_token": ensure_csrf(),
    }


# ============================================================
# REQUEST PROTECTION
# ============================================================

@bp.before_request
def protect_mutations():
    """
    Protect normal form mutations with CSRF.

    JSON API requests are intentionally excluded because the
    API endpoints use authenticated browser sessions and their
    JavaScript requests do not submit a traditional form token.
    """

    if request.method in {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }:

        excluded_endpoints = {
            "main.login",
            "main.setup_status",
            "main.health",
            "main.api_health",
        }

        if request.endpoint not in excluded_endpoints:

            if not csrf_ok() and not request.is_json:
                flash(
                    "Your session security token expired. "
                    "Please retry.",
                    "danger"
                )

                return redirect(
                    request.referrer
                    or url_for("main.dashboard")
                )


# ============================================================
# HOME
# ============================================================

@bp.get("/")
def index():
    """
    Redirect users to dashboard or login.
    """

    if current_user():
        return redirect(
            url_for("main.dashboard")
        )

    return redirect(
        url_for("main.login")
    )


# ============================================================
# LOGIN
# ============================================================

@bp.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if current_user():
        return redirect(
            url_for("main.dashboard")
        )

    if request.method == "POST":

        username = (
            request.form.get(
                "username",
                ""
            ).strip()
        )

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            username=username
        ).first()

        if (
            user
            and user.active
            and check_password_hash(
                user.password_hash,
                password
            )
        ):

            session.clear()

            session["user_id"] = user.id

            session["csrf_token"] = (
                secrets.token_urlsafe(32)
            )

            session["logged_in_at"] = (
                datetime.now(
                    timezone.utc
                ).isoformat()
            )

            user.last_login_at = (
                datetime.now(timezone.utc)
            )

            db.session.commit()

            audit(
                user.username,
                "login",
                "user",
                str(user.id)
            )

            flash(
                f"Welcome back, {user.name}.",
                "success"
            )

            return redirect(
                request.args.get("next")
                or url_for("main.dashboard")
            )

        flash(
            "Invalid username or password.",
            "danger"
        )

    return render_template(
        "auth.html",
        mode="login",
        **base_context()
    )


# ============================================================
# SIGNUP
# ============================================================

@bp.route(
    "/signup",
    methods=["GET", "POST"]
)
def signup():

    if current_user():
        return redirect(
            url_for("main.dashboard")
        )

    if request.method == "POST":

        username = (
            request.form.get(
                "username",
                ""
            ).strip()
        )

        password = request.form.get(
            "password",
            ""
        )

        name = (
            request.form.get(
                "name",
                ""
            ).strip()
        )

        email = (
            request.form.get(
                "email",
                ""
            ).strip()
        )

        if (
            len(username) < 3
            or len(password) < 8
            or not name
            or "@" not in email
        ):

            flash(
                "Enter a valid name, email, username "
                "and a password of at least 8 characters.",
                "danger"
            )

        elif User.query.filter_by(
            username=username
        ).first():

            flash(
                "That username is already in use.",
                "danger"
            )

        else:

            user = User(
                username=username,
                password_hash=generate_password_hash(
                    password
                ),
                role="user",
                name=name,
                email=email,
            )

            db.session.add(user)
            db.session.commit()

            audit(
                username,
                "signup",
                "user",
                str(user.id)
            )

            flash(
                "Account created. You can now sign in.",
                "success"
            )

            return redirect(
                url_for("main.login")
            )

    return render_template(
        "auth.html",
        mode="signup",
        **base_context()
    )


# ============================================================
# LOGOUT
# ============================================================

@bp.post("/logout")
@login_required
def logout():

    user = current_user()

    audit(
        user.username,
        "logout",
        "user",
        str(user.id)
    )

    session.clear()

    flash(
        "Signed out safely.",
        "success"
    )

    return redirect(
        url_for("main.login")
    )


# ============================================================
# DASHBOARD
# ============================================================

@bp.get("/dashboard")
@login_required
def dashboard():

    projects = (
        Project.query
        .order_by(Project.updated_at.desc())
        .all()
    )

    project_rows = [
        (p, project_stats(p))
        for p in projects
    ]

    stats = [
        stats
        for _, stats in project_rows
    ]

    summary = {
        "projects": len(projects),

        "active": sum(
            p.status in {
                "Planning",
                "In Progress",
                "Review",
            }
            for p in projects
        ),

        "completed": sum(
            p.status == "Completed"
            for p in projects
        ),

        "avg_compliance": (
            sum(
                s["excellent_percent"]
                for s in stats
            ) / len(stats)
        ) if stats else 0,

        "fails": sum(
            s["fail_count"]
            for s in stats
        ),

        "reviews": sum(
            s["need_review_count"]
            for s in stats
        ),
    }

    recent = (
        AuditLog.query
        .order_by(
            AuditLog.created_at.desc()
        )
        .limit(8)
        .all()
    )

    return render_template(
        "dashboard.html",
        projects=projects,
        project_rows=project_rows,
        summary=summary,
        recent=recent,
        **base_context()
    )


# ============================================================
# NEW PROJECT
# ============================================================

@bp.route(
    "/projects/new",
    methods=["GET", "POST"]
)
@login_required
def new_project():

    if request.method == "POST":

        try:

            p = create_project(
                request.form
            )

            audit(
                current_user().username,
                "create",
                "project",
                p.id,
                {"name": p.name}
            )

            flash(
                f"Project {p.name} created.",
                "success"
            )

            return redirect(
                url_for(
                    "main.project_detail",
                    pid=p.id
                )
            )

        except Exception as e:

            db.session.rollback()

            current_app.logger.exception(
                "project create failed"
            )

            flash(
                f"Could not create project: {e}",
                "danger"
            )

    return render_template(
        "project_form.html",
        project=None,
        **base_context(
            status_options=STATUS_OPTIONS,
            assessment_types=ASSESSMENT_TYPE_CODES,
            assessment_standards=ASSESSMENT_STANDARD_CODES,
        )
    )


# ============================================================
# EDIT PROJECT
# ============================================================

@bp.route(
    "/projects/<pid>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit_project(pid):

    p = project_or_404(pid)

    if request.method == "POST":

        p.name = (
            request.form.get(
                "name",
                ""
            ).strip()
        )

        p.manager = (
            request.form.get(
                "manager",
                ""
            ).strip()
        )

        p.description = (
            request.form.get(
                "description",
                ""
            ).strip()
        )

        p.status = request.form.get(
            "status",
            "Planning"
        )

        p.evaluated_by = (
            request.form.get(
                "evaluated_by",
                ""
            ).strip()
        )

        p.prepared_by = (
            request.form.get(
                "prepared_by",
                ""
            ).strip()
        )

        if request.form.get("start_date"):

            p.start_date = datetime.strptime(
                request.form["start_date"],
                "%Y-%m-%d"
            ).date()

        if request.form.get("target_date"):

            p.target_date = datetime.strptime(
                request.form["target_date"],
                "%Y-%m-%d"
            ).date()

        p.updated_at = datetime.now(
            timezone.utc
        )

        db.session.commit()

        audit(
            current_user().username,
            "update",
            "project",
            p.id,
            {"name": p.name}
        )

        flash(
            "Project updated.",
            "success"
        )

        return redirect(
            url_for(
                "main.project_detail",
                pid=p.id
            )
        )

    return render_template(
        "project_form.html",
        project=p,
        **base_context(
            status_options=STATUS_OPTIONS,
            assessment_types=ASSESSMENT_TYPE_CODES,
            assessment_standards=ASSESSMENT_STANDARD_CODES,
        )
    )


# ============================================================
# DELETE PROJECT
# ============================================================

@bp.post(
    "/projects/<pid>/delete"
)
@admin_required
def delete_project(pid):

    p = project_or_404(pid)

    name = p.name

    db.session.delete(p)
    db.session.commit()

    audit(
        current_user().username,
        "delete",
        "project",
        pid,
        {"name": name}
    )

    flash(
        f"Deleted {name}.",
        "success"
    )

    return redirect(
        url_for("main.dashboard")
    )


# ============================================================
# PROJECT DETAIL
# ============================================================

@bp.get(
    "/projects/<pid>"
)
@login_required
def project_detail(pid):

    p = project_or_404(pid)

    stats = project_stats(p)

    template = template_for(
        p.assessment_type_code
    )

    return render_template(
        "project_detail.html",
        project=p,
        stats=stats,
        template=template,
        **base_context()
    )


# ============================================================
# CHECKLIST
#
# IMPORTANT:
# There is intentionally NO:
#
#     main.checklist_level
#
# endpoint here.
#
# The existing frontend uses:
#
#     main.api_checklist_save
#
# ============================================================

@bp.route(
    "/projects/<pid>/checklist",
    methods=["GET", "POST"]
)
@login_required
def checklist(pid):

    p = project_or_404(pid)

    template = template_for(
        p.assessment_type_code
    )

    # --------------------------------------------------------
    # NORMAL CHECKLIST POST
    # --------------------------------------------------------

    if request.method == "POST":

        payload = (
            request.get_json(
                silent=True
            )
            if request.is_json
            else request.form.get(
                "payload"
            )
        )

        try:

            data = (
                json.loads(payload)
                if isinstance(payload, str)
                else payload
            )

            if not isinstance(data, dict):
                raise ValueError(
                    "Invalid checklist payload"
                )

            p.checklist_data = data

            p.updated_at = datetime.now(
                timezone.utc
            )

            db.session.commit()

            audit(
                current_user().username,
                "update",
                "checklist",
                p.id,
                {"autosave": True}
            )

            if request.is_json:

                return jsonify(
                    ok=True,
                    stats=project_stats(p)
                )

            return redirect(
                url_for(
                    "main.checklist",
                    pid=p.id
                )
            )

        except Exception as e:

            db.session.rollback()

            current_app.logger.exception(
                "Checklist save failed for project %s",
                pid
            )

            if request.is_json:

                return jsonify(
                    ok=False,
                    error=str(e)
                ), 400

            flash(
                f"Could not save checklist: {e}",
                "danger"
            )

            return redirect(
                url_for(
                    "main.checklist",
                    pid=p.id
                )
            )

    # --------------------------------------------------------
    # CHECKLIST GET
    # --------------------------------------------------------

    section = request.args.get(
        "section"
    )

    stats = project_stats(p)

    return render_template(
        "checklist.html",
        project=p,
        template=template,
        stats=stats,
        selected_section=section,
        response_options=RESPONSE_OPTIONS,
        **base_context()
    )


# ============================================================
# CHECKLIST API SAVE
# ============================================================

@bp.post(
    "/api/projects/<pid>/checklist"
)
@login_required
def api_checklist_save(pid):

    p = project_or_404(pid)

    data = request.get_json(
        silent=True
    ) or {}

    if not isinstance(data, dict):

        return jsonify(
            ok=False,
            error="Invalid JSON"
        ), 400

    try:

        p.checklist_data = data

        p.updated_at = datetime.now(
            timezone.utc
        )

        db.session.commit()

        audit(
            current_user().username,
            "update",
            "checklist",
            p.id,
            {"autosave": True}
        )

        return jsonify(
            ok=True,
            stats=project_stats(p)
        )

    except Exception as e:

        db.session.rollback()

        current_app.logger.exception(
            "Checklist API save failed for project %s",
            pid
        )

        return jsonify(
            ok=False,
            error=str(e)
        ), 500


# ============================================================
# IMPORT CHECKLIST JSON
# ============================================================

@bp.post(
    "/projects/<pid>/import-json"
)
@login_required
def import_json(pid):

    p = project_or_404(pid)

    f = request.files.get(
        "json_file"
    )

    if not f or not f.filename:

        flash(
            "Choose a JSON export file.",
            "danger"
        )

        return redirect(
            url_for(
                "main.checklist",
                pid=pid
            )
        )

    try:

        payload = json.load(f)

        checklist_data = (
            payload.get("checklist")
            if isinstance(payload, dict)
            else None
        )

        if not isinstance(
            checklist_data,
            dict
        ):

            raise ValueError(
                "The JSON file does not contain "
                "a valid checklist object."
            )

        p.checklist_data = checklist_data

        p.updated_at = datetime.now(
            timezone.utc
        )

        db.session.commit()

        audit(
            current_user().username,
            "import",
            "checklist",
            p.id,
            {
                "filename": secure_filename(
                    f.filename
                )
            }
        )

        flash(
            "Checklist JSON imported successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        current_app.logger.exception(
            "Checklist JSON import failed"
        )

        flash(
            f"Import failed: {e}",
            "danger"
        )

    return redirect(
        url_for(
            "main.checklist",
            pid=pid
        )
    )


# ============================================================
# REPORT
# ============================================================

@bp.get(
    "/projects/<pid>/report"
)
@login_required
def report(pid):

    p = project_or_404(pid)

    scope = request.args.get(
        "scope",
        "all"
    )

    section = request.args.get(
        "section"
    )

    template = template_for(
        p.assessment_type_code
    )

    stats = calculate_completion(
        p.checklist_data or {},
        template,
        section
        if scope == "section"
        else None
    )

    return render_template(
        "report.html",
        project=p,
        stats=stats,
        template=template,
        scope=scope,
        section=section,
        now=datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d %H:%M UTC"
        ),
        **base_context()
    )


# ============================================================
# EXPORT PROJECT JSON
# ============================================================

@bp.get(
    "/projects/<pid>/export.json"
)
@login_required
def export_json(pid):

    p = project_or_404(pid)

    payload = {
        "metadata": {
            "id": p.id,
            "name": p.name,
            "manager": p.manager,
            "description": p.description,
            "start_date": (
                p.start_date.isoformat()
                if p.start_date
                else None
            ),
            "target_date": (
                p.target_date.isoformat()
                if p.target_date
                else None
            ),
            "status": p.status,
            "evaluated_by": p.evaluated_by,
            "prepared_by": p.prepared_by,
            "assessment_type_code": (
                p.assessment_type_code
            ),
            "assessment_type": (
                p.assessment_type
            ),
            "assessment_standard_code": (
                p.assessment_standard_code
            ),
            "assessment_standard": (
                p.assessment_standard
            ),
            "created_at": (
                p.created_at.isoformat()
                if p.created_at
                else None
            ),
        },

        "checklist": p.checklist_data,
    }

    audit(
        current_user().username,
        "export",
        "project",
        p.id,
        {"format": "json"}
    )

    content = json.dumps(
        payload,
        indent=2,
        default=str
    ).encode()

    return send_file(
        io.BytesIO(content),
        mimetype="application/json",
        as_attachment=True,
        download_name=f"{p.id}.json"
    )


# ============================================================
# DOCUMENTS
# ============================================================

@bp.get("/documents")
@login_required
def documents():

    category = (
        request.args.get(
            "category",
            ""
        ).strip()
    )

    q = (
        request.args.get(
            "q",
            ""
        ).strip().lower()
    )

    query = (
        Document.query
        .order_by(
            Document.created_at.desc()
        )
    )

    docs = query.all()

    if category:

        docs = [
            d
            for d in docs
            if d.category == category
        ]

    if q:

        docs = [
            d
            for d in docs
            if (
                q in d.original_name.lower()
                or q in (
                    d.description or ""
                ).lower()
                or any(
                    q in str(tag).lower()
                    for tag in (
                        d.tags or []
                    )
                )
            )
        ]

    return render_template(
        "documents.html",
        documents=docs,
        categories=DOCUMENT_CATEGORIES,
        selected_category=category,
        q=q,
        **base_context()
    )


# ============================================================
# DOCUMENT UPLOAD
# ============================================================

@bp.post(
    "/documents/upload"
)
@login_required
def document_upload():

    f = request.files.get(
        "file"
    )

    if not f or not f.filename:

        flash(
            "Choose a file to upload.",
            "danger"
        )

        return redirect(
            url_for("main.documents")
        )

    try:

        data = f.read()

        doc_id = (
            "DOC-"
            + datetime.now(
                timezone.utc
            ).strftime(
                "%Y%m%d%H%M%S"
            )
            + secrets.token_hex(2)
        )

        tags = [
            x.strip()
            for x in request.form.get(
                "tags",
                ""
            ).split(",")
            if x.strip()
        ]

        doc = Document(
            id=doc_id,
            original_name=(
                secure_filename(
                    f.filename
                )
                or f.filename
            ),
            content_type=(
                f.mimetype
                or "application/octet-stream"
            ),
            category=request.form.get(
                "category",
                "Other"
            ),
            description=(
                request.form.get(
                    "description",
                    ""
                ).strip()
            ),
            tags=tags,
            uploaded_by=current_user().name,
            file_data=data,
            file_size=len(data),
        )

        db.session.add(doc)

        db.session.commit()

        audit(
            current_user().username,
            "upload",
            "document",
            doc.id,
            {
                "name": doc.original_name,
                "size": len(data),
            }
        )

        flash(
            "Document uploaded successfully.",
            "success"
        )

    except Exception as e:

        db.session.rollback()

        current_app.logger.exception(
            "Document upload failed"
        )

        flash(
            f"Upload failed: {e}",
            "danger"
        )

    return redirect(
        url_for("main.documents")
    )


# ============================================================
# DOCUMENT DOWNLOAD
# ============================================================

@bp.get(
    "/documents/<doc_id>/download"
)
@login_required
def document_download(doc_id):

    d = Document.query.get_or_404(
        doc_id
    )

    audit(
        current_user().username,
        "download",
        "document",
        d.id
    )

    return send_file(
        io.BytesIO(d.file_data),
        mimetype=d.content_type,
        as_attachment=True,
        download_name=d.original_name
    )


# ============================================================
# DOCUMENT DELETE
# ============================================================

@bp.post(
    "/documents/<doc_id>/delete"
)
@login_required
def document_delete(doc_id):

    d = Document.query.get_or_404(
        doc_id
    )

    name = d.original_name

    db.session.delete(d)

    db.session.commit()

    audit(
        current_user().username,
        "delete",
        "document",
        doc_id,
        {"name": name}
    )

    flash(
        "Document deleted.",
        "success"
    )

    return redirect(
        url_for("main.documents")
    )


# ============================================================
# ADMIN
# ============================================================

@bp.route(
    "/admin",
    methods=["GET", "POST"]
)
@admin_required
def admin():

    tab = request.args.get(
        "tab",
        "users"
    )

    if request.method == "POST":

        action = request.form.get(
            "action"
        )

        # ----------------------------------------------------
        # CREATE USER
        # ----------------------------------------------------

        if action == "create_user":

            username = (
                request.form.get(
                    "username",
                    ""
                ).strip()
            )

            pw = request.form.get(
                "password",
                ""
            )

            name = (
                request.form.get(
                    "name",
                    ""
                ).strip()
            )

            email = (
                request.form.get(
                    "email",
                    ""
                ).strip()
            )

            role = request.form.get(
                "role",
                "user"
            )

            if User.query.filter_by(
                username=username
            ).first():

                flash(
                    "Username already exists.",
                    "danger"
                )

            else:

                u = User(
                    username=username,
                    password_hash=generate_password_hash(
                        pw
                    ),
                    name=name,
                    email=email,
                    role=role,
                )

                db.session.add(u)

                db.session.commit()

                audit(
                    current_user().username,
                    "create",
                    "user",
                    str(u.id)
                )

                flash(
                    "User created.",
                    "success"
                )

        # ----------------------------------------------------
        # UPDATE USER
        # ----------------------------------------------------

        elif action == "update_role":

            u = User.query.get(
                int(
                    request.form["user_id"]
                )
            )

            if u:

                u.role = request.form.get(
                    "role",
                    "user"
                )

                u.active = (
                    request.form.get(
                        "active"
                    )
                    == "on"
                )

                db.session.commit()

                audit(
                    current_user().username,
                    "update",
                    "user",
                    str(u.id),
                    {
                        "role": u.role,
                        "active": u.active,
                    }
                )

                flash(
                    "User updated.",
                    "success"
                )

        # ----------------------------------------------------
        # DELETE USER
        # ----------------------------------------------------

        elif action == "delete_user":

            u = User.query.get(
                int(
                    request.form[
                        "user_id"
                    ]
                )
            )

            if (
                u
                and u.id != current_user().id
            ):

                db.session.delete(u)

                db.session.commit()

                audit(
                    current_user().username,
                    "delete",
                    "user",
                    str(u.id)
                )

                flash(
                    "User deleted.",
                    "success"
                )

        # ----------------------------------------------------
        # SAVE TEMPLATE
        # ----------------------------------------------------

        elif action == "save_template":

            code = request.form.get(
                "code",
                "SQCR"
            )

            raw = request.form.get(
                "template_json",
                "{}"
            )

            row = ChecklistTemplate.query.get(
                code
            )

            if row:

                try:

                    row.data = json.loads(
                        raw
                    )

                    db.session.commit()

                    audit(
                        current_user().username,
                        "update",
                        "template",
                        code
                    )

                    flash(
                        "Checklist template saved.",
                        "success"
                    )

                except Exception as e:

                    db.session.rollback()

                    flash(
                        f"Template save failed: {e}",
                        "danger"
                    )

    users = (
        User.query
        .order_by(
            User.created_at.desc()
        )
        .all()
    )

    templates = (
        ChecklistTemplate.query
        .order_by(
            ChecklistTemplate.code
        )
        .all()
    )

    projects = (
        Project.query
        .order_by(
            Project.created_at.desc()
        )
        .all()
    )

    logs = (
        AuditLog.query
        .order_by(
            AuditLog.created_at.desc()
        )
        .limit(40)
        .all()
    )

    return render_template(
        "admin.html",
        users=users,
        templates=templates,
        projects=projects,
        logs=logs,
        tab=tab,
        **base_context()
    )


# ============================================================
# ADMIN PROJECT DELETE
# ============================================================

@bp.post(
    "/admin/projects/<pid>/delete"
)
@admin_required
def admin_project_delete(pid):

    return delete_project(pid)


# ============================================================
# ABOUT
# ============================================================

@bp.get("/about")
def about():

    return render_template(
        "about.html",
        **base_context()
    )


# ============================================================
# HEALTH
# ============================================================

@bp.get("/health")
def health():

    if not current_app.config.get(
        "DB_CONFIGURED"
    ):

        from .config import DB_CONFIG_ERROR

        return jsonify(
            status="degraded",
            database="not_configured",
            detail=DB_CONFIG_ERROR,
        ), 503

    try:

        db.session.execute(
            db.text("SELECT 1")
        )

        return jsonify(
            status="ok",
            database="connected"
        )

    except Exception as e:

        current_app.logger.exception(
            "Database health check failed"
        )

        return jsonify(
            status="degraded",
            database="error",
            detail=str(e),
        ), 503


# ============================================================
# SETUP STATUS
# ============================================================

@bp.get("/setup-status")
def setup_status():

    return jsonify(
        database_url_configured=bool(
            current_app.config.get(
                "DB_CONFIGURED"
            )
        )
    )
