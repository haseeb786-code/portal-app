import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from core.database import Database
from core.extractor import OdoCustExtractor
from core.auth import OdoCustAuth
import config

db = Database(config.DATABASE_PATH)
auth = OdoCustAuth(config.ODOCUST_BASE_URL, config.ODOCUST_USERNAME, config.ODOCUST_PASSWORD, config.ODOCUST_SESSION_ID)
extractor = OdoCustExtractor(config.ODOCUST_BASE_URL)

session = auth.get_authenticated_session()
r = session.get(f"{auth.base_url}/student/results", timeout=25, verify=False)
if r.status_code == 200:
    info = extractor.parse_academic_results(r.text)
    if "current_cgpa" in info:
        db.set_student_profile("current_cgpa", str(info["current_cgpa"]))
        db.set_student_profile("completed_credits", str(info["completed_credits"]))
        db.set_student_profile("latest_sgpa", str(info["latest_sgpa"]))
        db.set_student_profile("latest_term", str(info["latest_term"]))
        db.set_student_profile("academic_transcript", json.dumps(info["terms"]))
        print("SUCCESS: Live CGPA & Transcript synced into database!")
        print(f"CGPA: {info['current_cgpa']}")
        print(f"Latest SGPA: {info['latest_sgpa']} ({info['latest_term']})")
        print(f"Completed Credits: {info['completed_credits']}")
        print(f"Total Semesters: {len(info['terms'])}")
    else:
        print("Error: Could not parse CGPA from results page.")
else:
    print(f"Failed with status code: {r.status_code}")
