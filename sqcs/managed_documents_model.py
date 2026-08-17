from datetime import datetime, timezone
from .extensions import db

def utcnow():
    return datetime.now(timezone.utc)

class ManagedDocument(db.Model):
    __tablename__ = "managed_documents"

    id = db.Column(db.String(40), primary_key=True)
    project_id = db.Column(db.String(32), nullable=True, index=True)
    doc_type = db.Column(db.String(20), nullable=False, index=True)  # REPORT, SRS, SAD
    title = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text, default="")
    content = db.Column(db.Text, nullable=False, default="")
    created_by = db.Column(db.String(180), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
