import json
import re
import secrets
from datetime import date
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db
from .models import User, Project, ChecklistTemplate, Document, AuditLog, utcnow

BASE_DIR = Path(__file__).resolve().parent.parent

ASSESSMENT_TYPE_CODES = {
    'SQCR': 'Software Quality Compliance Review',
    'CODE_REVIEW': 'Code Review',
    'SECURITY_AUDIT': 'Security Audit',
    'QA_ASSESSMENT': 'Quality Assurance Assessment',
    'OTHER': 'Other',
}
ASSESSMENT_STANDARD_CODES = {
    'EAII-SDQS': 'Ethiopian Artificial Intelligence Institute Software Development and Quality Standards (EAII-SDQS)',
    'ISO-9001': 'ISO 9001 Quality Management System',
    'IEC-62443': 'IEC 62443 Industrial Automation and Control Systems Security',
    'CMMI': 'Capability Maturity Model Integration',
    'OTHER': 'Other',
}
DOCUMENT_CATEGORIES = [
    'Software Quality assurance',
    'Software Standard Documents',
    'Software Standard Checklist',
    'Software Testing Documents',
    'Architecture & Design',
    'Security & Compliance',
    'Other',
]
RESPONSE_OPTIONS = ['Excellent', 'Need Review', 'Fail', 'N/A']
STATUS_OPTIONS = ['Planning', 'In Progress', 'Review', 'Completed', 'On Hold']


def safe_json_load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_templates():
    defaults = {
        'SQCR': ('Software Quality Compliance Review', BASE_DIR / 'checklist_template_SQCR.json'),
        'LEGACY': ('SQCS Legacy Checklist', BASE_DIR / 'checklist_template.json'),
    }
    for code, (name, path) in defaults.items():
        if ChecklistTemplate.query.get(code) is None:
            db.session.add(ChecklistTemplate(code=code, name=name, data=safe_json_load(path)))
    db.session.commit()


def ensure_admin():
    import os
    username = os.getenv('ADMIN_USERNAME', 'admin')
    password = os.getenv('ADMIN_PASSWORD', 'admin123')
    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username, password_hash=generate_password_hash(password), role='admin',
                    name=os.getenv('ADMIN_NAME', 'System Administrator'),
                    email=os.getenv('ADMIN_EMAIL', 'admin@example.com'))
        db.session.add(user)
        db.session.commit()


def audit(username, action, entity_type=None, entity_id=None, details=None):
    db.session.add(AuditLog(username=username, action=action, entity_type=entity_type,
                            entity_id=entity_id, details=details or {}))
    db.session.commit()


def template_for(code='SQCR'):
    row = ChecklistTemplate.query.get(code)
    if not row:
        row = ChecklistTemplate.query.get('SQCR')
    return row.data if row else {}


def normalize(text):
    return re.sub(r'[^a-z0-9]+', ' ', str(text or '')).strip().lower()


def find_item_data(pool, item_id, description=''):
    if not isinstance(pool, dict):
        return None
    if item_id in pool:
        return pool[item_id]
    ni = normalize(item_id)
    for key, value in pool.items():
        if normalize(key) == ni:
            return value
    nd = normalize(description)
    if nd:
        for value in pool.values():
            if isinstance(value, dict) and normalize(value.get('description')) == nd:
                return value
        desired = set(nd.split())
        best, score = None, 0.0
        for value in pool.values():
            if not isinstance(value, dict):
                continue
            tokens = set(normalize(value.get('description')).split())
            if not tokens:
                continue
            s = len(desired & tokens) / max(len(desired), len(tokens))
            if s > score:
                best, score = value, s
        if score >= .5:
            return best
    return None


def calculate_completion(checklist_data, template_data, specific_section=None):
    stats = dict(total_items=0, excellent_count=0, need_review_count=0, fail_count=0,
                 na_count=0, unanswered_count=0, section_stats=[])
    sections = [specific_section] if specific_section else list(dict.fromkeys(list(template_data) + list(checklist_data)))
    for section in sections:
        section_items = section_exc = section_review = section_fail = section_na = section_un = 0
        tsec = template_data.get(section, {}) if isinstance(template_data, dict) else {}
        csec = checklist_data.get(section, {}) if isinstance(checklist_data, dict) else {}
        for subsection, items in (tsec.items() if isinstance(tsec, dict) else []):
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    section_items += 1
                    data = find_item_data(csec.get(subsection, {}), item.get('id'), item.get('description', ''))
                    response = str((data or {}).get('response', '')).strip().lower()
                    if response == 'excellent': section_exc += 1
                    elif response in {'need review', 'review', 'need_review'}: section_review += 1
                    elif response == 'fail': section_fail += 1
                    elif response in {'n/a', 'na', 'not applicable'}: section_na += 1
                    else: section_un += 1
            elif isinstance(items, dict):
                for item_id, item in items.items():
                    if not isinstance(item, dict): continue
                    section_items += 1
                    data = find_item_data(csec.get(subsection, {}), item_id, item.get('description', ''))
                    response = str((data or {}).get('response', '')).strip().lower()
                    if response == 'excellent': section_exc += 1
                    elif response in {'need review', 'review', 'need_review'}: section_review += 1
                    elif response == 'fail': section_fail += 1
                    elif response in {'n/a', 'na', 'not applicable'}: section_na += 1
                    else: section_un += 1
        # preserve extra persisted items if the template changed
        if section not in template_data and isinstance(csec, dict):
            for subsection, items in csec.items():
                if not isinstance(items, dict): continue
                for item in items.values():
                    if not isinstance(item, dict): continue
                    section_items += 1
                    response = str(item.get('response', '')).strip().lower()
                    if response == 'excellent': section_exc += 1
                    elif response in {'need review', 'review', 'need_review'}: section_review += 1
                    elif response == 'fail': section_fail += 1
                    elif response in {'n/a', 'na', 'not applicable'}: section_na += 1
                    else: section_un += 1
        if section_items:
            stats['total_items'] += section_items
            stats['excellent_count'] += section_exc
            stats['need_review_count'] += section_review
            stats['fail_count'] += section_fail
            stats['na_count'] += section_na
            stats['unanswered_count'] += section_un
            stats['section_stats'].append({
                'section': section, 'total_items': section_items,
                'excellent': section_exc, 'need_review': section_review,
                'fail': section_fail, 'na': section_na, 'unanswered': section_un,
                'completion': (section_exc / section_items) * 100,
            })
    stats['excellent_percent'] = (stats['excellent_count'] / stats['total_items'] * 100) if stats['total_items'] else 0
    stats['need_review_percent'] = (stats['need_review_count'] / stats['total_items'] * 100) if stats['total_items'] else 0
    stats['fail_percent'] = (stats['fail_count'] / stats['total_items'] * 100) if stats['total_items'] else 0
    stats['na_percent'] = (stats['na_count'] / stats['total_items'] * 100) if stats['total_items'] else 0
    return stats


def new_project_checklist(template_data):
    result = {}
    for section, subsections in template_data.items():
        result[section] = {}
        for subsection, items in subsections.items():
            result[section][subsection] = {}
            source = items if isinstance(items, list) else [dict(v, id=k) if isinstance(v, dict) else {'id': k, 'description': str(v)} for k, v in items.items()]
            for item in source:
                result[section][subsection][item['id']] = {'description': item.get('description', ''), 'response': '', 'feedback': '', 'last_modified': None}
    return result


def create_project(form):
    code = form.get('assessment_type_code', 'SQCR')
    std = form.get('assessment_standard_code', 'EAII-SDQS')
    assessment_type = form.get('assessment_type_custom', '').strip() if code == 'OTHER' else ASSESSMENT_TYPE_CODES.get(code, ASSESSMENT_TYPE_CODES['SQCR'])
    assessment_standard = form.get('assessment_standard_custom', '').strip() if std == 'OTHER' else ASSESSMENT_STANDARD_CODES.get(std, ASSESSMENT_STANDARD_CODES['EAII-SDQS'])
    project_id = 'PRJ-' + utcnow().strftime('%Y%m%d%H%M%S') + secrets.token_hex(1)
    start = date.fromisoformat(form['start_date']) if form.get('start_date') else None
    target = date.fromisoformat(form['target_date']) if form.get('target_date') else None
    p = Project(id=project_id, name=form['name'].strip(), manager=form['manager'].strip(), description=form.get('description','').strip(),
                start_date=start, target_date=target, status=form.get('status','Planning'), evaluated_by=form.get('evaluated_by','').strip(),
                prepared_by=form.get('prepared_by','').strip(), assessment_type_code=code, assessment_type=assessment_type,
                assessment_standard_code=std, assessment_standard=assessment_standard, checklist_data=new_project_checklist(template_for(code)))
    db.session.add(p)
    db.session.commit()
    return p


def project_stats(project):
    return calculate_completion(project.checklist_data or {}, template_for(project.assessment_type_code))
