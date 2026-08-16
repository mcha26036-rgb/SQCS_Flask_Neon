"""Import legacy SQCS JSON projects/documents into the Flask + Neon schema.
Run after DATABASE_URL is configured:
    python scripts/import_legacy.py --source /path/to/old/SQCS_Platform-main
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqcs import create_app
from sqcs.extensions import db
from sqcs.models import Project, Document


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',required=True); args=ap.parse_args()
    root=Path(args.source); app=create_app()
    with app.app_context():
        projects=root/'projects'
        if projects.exists():
            for folder in projects.iterdir():
                pj=folder/'project.json'; cj=folder/'checklist.json'
                if not pj.exists(): continue
                meta=json.load(open(pj,encoding='utf-8')); checklist=json.load(open(cj,encoding='utf-8')) if cj.exists() else {}
                if Project.query.get(meta['id']): continue
                # Keep migration tolerant of old field layouts.
                p=Project(id=meta['id'],name=meta.get('name',meta['id']),manager=meta.get('manager',''),description=meta.get('description',''),
                          status=meta.get('status','Planning'),evaluated_by=meta.get('evaluated_by',''),prepared_by=meta.get('prepared_by',''),
                          assessment_type_code=meta.get('assessment_type_code','SQCR'),assessment_type=meta.get('assessment_type','Software Quality Compliance Review'),
                          assessment_standard_code=meta.get('assessment_standard_code','EAII-SDQS'),assessment_standard=meta.get('assessment_standard',''),checklist_data=checklist)
                if meta.get('start_date'): p.start_date=__import__('datetime').date.fromisoformat(meta['start_date'])
                if meta.get('target_date'): p.target_date=__import__('datetime').date.fromisoformat(meta['target_date'])
                db.session.add(p)
        db.session.commit()
        print('Legacy projects imported. Document blobs are intentionally not copied automatically; upload them through the web UI or extend this importer for your storage policy.')

if __name__=='__main__': main()
