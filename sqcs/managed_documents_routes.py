from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort
from io import BytesIO
from datetime import datetime, timezone
import html
import secrets

from .extensions import db
from .models import Project
from .managed_documents_model import ManagedDocument

managed_bp = Blueprint("managed_docs", __name__, url_prefix="/managed-documents")

DOC_TYPES = ("REPORT", "SRS", "SAD")

def _csrf_ok():
    from .routes import ensure_csrf
    token = request.form.get("_csrf") or request.headers.get("X-CSRF-Token")
    current = ensure_csrf()
    return bool(token and current and secrets.compare_digest(token, current))

def _user():
    from .routes import current_user
    return current_user()

def _require_login():
    user = _user()
    if not user or not user.active:
        abort(401)
    return user

def _doc_or_404(doc_id):
    doc = ManagedDocument.query.get(doc_id)
    if not doc:
        abort(404)
    return doc

def _html_document(doc, project=None, include_title=True):
    title = html.escape(doc.title)
    body = doc.content or ""
    project_name = html.escape(project.name) if project else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;line-height:1.6}}
h1{{margin-bottom:4px}} .meta{{color:#666;margin-bottom:28px}}
@media print{{body{{margin:0;max-width:none}} .no-print{{display:none}}}}
</style></head><body>
{"<h1>"+title+"</h1>" if include_title else ""}
<div class="meta">{doc.doc_type}{" · "+project_name if project_name else ""}</div>
{body}
</body></html>"""

def _full_html(project_id):
    project = Project.query.get_or_404(project_id)
    docs = ManagedDocument.query.filter_by(project_id=project_id).order_by(
        ManagedDocument.doc_type, ManagedDocument.updated_at.desc()
    ).all()
    from .services import project_stats
    stats = project_stats(project)
    level = "FAIL" if stats["fail_count"] else (
        "EXCELLENT" if stats["total_items"] and stats["unanswered_count"] == 0 and
        stats["excellent_count"] == stats["total_items"] else "PASS"
    )
    completed = stats["total_items"] - stats["unanswered_count"]
    progress = round(completed / stats["total_items"] * 100) if stats["total_items"] else 0
    sections = [
        f"<h1>{html.escape(project.name)}</h1>",
        f"<p><b>Level:</b> {level} &nbsp; <b>Progress:</b> {completed}/{stats['total_items']} &nbsp; <b>Completion:</b> {progress}%</p>"
    ]
    for doc in docs:
        sections.append(f"<hr><h2>{html.escape(doc.doc_type)} — {html.escape(doc.title)}</h2>{doc.content or ''}")
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(project.name)} — Full System</title>
<style>body{{font-family:Arial,sans-serif;max-width:1000px;margin:40px auto;padding:0 20px;line-height:1.6}}
@media print{{body{{margin:0;max-width:none}}}}</style></head><body>{''.join(sections)}</body></html>"""

@managed_bp.get("/")
def index():
    _require_login()
    project_id = request.args.get("project_id")
    projects = Project.query.order_by(Project.updated_at.desc()).all()
    docs = ManagedDocument.query.order_by(ManagedDocument.updated_at.desc()).all()
    if project_id:
        docs = [d for d in docs if d.project_id == project_id]
    return render_template("managed_documents.html", documents=docs, projects=projects,
                           selected_project=project_id, doc_types=DOC_TYPES)

@managed_bp.post("/create")
def create():
    user = _require_login()
    if not _csrf_ok(): abort(400)
    doc_type = request.form.get("doc_type", "REPORT").upper()
    if doc_type not in DOC_TYPES: abort(400)
    doc = ManagedDocument(
        id="MD-" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + secrets.token_hex(2),
        project_id=request.form.get("project_id") or None,
        doc_type=doc_type,
        title=request.form.get("title", "").strip() or f"New {doc_type}",
        description=request.form.get("description", "").strip(),
        content=request.form.get("content", ""),
        created_by=user.name,
    )
    db.session.add(doc); db.session.commit()
    flash("Document created.", "success")
    return redirect(url_for("managed_docs.index", project_id=doc.project_id))

@managed_bp.route("/<doc_id>/edit", methods=["GET", "POST"])
def edit(doc_id):
    _require_login()
    doc = _doc_or_404(doc_id)
    if request.method == "POST":
        if not _csrf_ok(): abort(400)
        doc.doc_type = request.form.get("doc_type", doc.doc_type).upper()
        if doc.doc_type not in DOC_TYPES: abort(400)
        doc.title = request.form.get("title", "").strip() or doc.title
        doc.description = request.form.get("description", "").strip()
        doc.content = request.form.get("content", "")
        doc.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("Document updated.", "success")
        return redirect(url_for("managed_docs.index", project_id=doc.project_id))
    return render_template("managed_document_edit.html", doc=doc, projects=Project.query.order_by(Project.name).all(),
                           doc_types=DOC_TYPES)

@managed_bp.post("/<doc_id>/delete")
def delete(doc_id):
    _require_login()
    if not _csrf_ok(): abort(400)
    doc = _doc_or_404(doc_id); project_id = doc.project_id
    db.session.delete(doc); db.session.commit()
    flash("Document deleted.", "success")
    return redirect(url_for("managed_docs.index", project_id=project_id))

@managed_bp.get("/<doc_id>/html")
def specific_html(doc_id):
    _require_login()
    doc = _doc_or_404(doc_id)
    project = Project.query.get(doc.project_id) if doc.project_id else None
    content = _html_document(doc, project)
    return send_file(BytesIO(content.encode("utf-8")), mimetype="text/html",
                     as_attachment=True, download_name=f"{doc.doc_type.lower()}_{doc.id}.html")

@managed_bp.get("/<doc_id>/print")
def specific_print(doc_id):
    _require_login()
    doc = _doc_or_404(doc_id)
    project = Project.query.get(doc.project_id) if doc.project_id else None
    return _html_document(doc, project)

@managed_bp.get("/full/<project_id>/html")
def full_html(project_id):
    _require_login()
    content = _full_html(project_id)
    return send_file(BytesIO(content.encode("utf-8")), mimetype="text/html",
                     as_attachment=True, download_name=f"project_{project_id}_full.html")

@managed_bp.get("/full/<project_id>/print")
def full_print(project_id):
    _require_login()
    return _full_html(project_id)
