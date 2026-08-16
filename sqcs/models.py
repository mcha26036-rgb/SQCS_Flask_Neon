from datetime import datetime, timezone
from .extensions import db


def utcnow():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(300), nullable=False)
    role = db.Column(db.String(30), nullable=False, default='user')
    name = db.Column(db.String(180), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime(timezone=True))


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(220), nullable=False, index=True)
    manager = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, default='')
    start_date = db.Column(db.Date)
    target_date = db.Column(db.Date)
    status = db.Column(db.String(40), nullable=False, default='Planning', index=True)
    evaluated_by = db.Column(db.String(180), default='')
    prepared_by = db.Column(db.String(180), default='')
    assessment_type_code = db.Column(db.String(40), nullable=False, default='SQCR')
    assessment_type = db.Column(db.String(255), nullable=False, default='Software Quality Compliance Review')
    assessment_standard_code = db.Column(db.String(40), nullable=False, default='EAII-SDQS')
    assessment_standard = db.Column(db.String(400), nullable=False)
    checklist_data = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class ChecklistTemplate(db.Model):
    __tablename__ = 'checklist_templates'
    code = db.Column(db.String(40), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    data = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.String(40), primary_key=True)
    original_name = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(180), nullable=False)
    category = db.Column(db.String(180), nullable=False)
    description = db.Column(db.Text, default='')
    tags = db.Column(db.JSON, nullable=False, default=list)
    uploaded_by = db.Column(db.String(180), nullable=False)
    file_data = db.Column(db.LargeBinary, nullable=False)
    file_size = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), index=True)
    action = db.Column(db.String(120), nullable=False, index=True)
    entity_type = db.Column(db.String(80))
    entity_id = db.Column(db.String(120))
    details = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False, index=True)
