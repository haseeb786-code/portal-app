import os
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from core.database import Database
from core.models import PriorityLevel, SubmissionStatus, ActivityType

def create_dashboard_app(database: Database, monitor_agent=None) -> FastAPI:
    app = FastAPI(title="ODOCUST Academic Monitor", version="1.0.0")

    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def serve_index():
        index_file = static_dir / "index.html"
        if not index_file.exists():
            return HTMLResponse("<h1>ODOCUST Monitor Dashboard Loading...</h1>", status_code=200)
        return FileResponse(index_file)

    @app.get("/api/overview")
    async def get_overview():
        summary = database.get_dashboard_summary()
        summary["portal_status"] = database.get_setting("portal_status", "OK")
        summary["portal_last_checked"] = database.get_setting("portal_last_checked", "")
        summary["portal_last_error"] = database.get_setting("portal_last_error", "")
        return summary

    @app.get("/api/courses")
    async def get_courses():
        courses = database.get_all_courses()
        all_activities = database.get_all_activities()
        
        result = []
        for c in courses:
            c_acts = [a for a in all_activities if a.course_id == c.course_id]
            pending = sum(1 for a in c_acts if a.submission_status not in (SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED) and a.activity_type in (ActivityType.ASSIGNMENT, ActivityType.PROJECT))
            result.append({
                "course_id": c.course_id,
                "name": c.name,
                "code": c.code,
                "instructor": c.instructor,
                "url": c.url,
                "attendance_pct": c.attendance_pct,
                "is_fyp": c.is_fyp,
                "last_synced": c.last_synced.isoformat() if c.last_synced else None,
                "total_activities": len(c_acts),
                "pending_tasks": pending
            })
        return result

    @app.get("/api/activities")
    async def get_activities(course_id: Optional[str] = None, activity_type: Optional[str] = None):
        activities = database.get_all_activities()
        if course_id:
            activities = [a for a in activities if a.course_id == course_id]
        if activity_type:
            activities = [a for a in activities if a.activity_type.value.lower() == activity_type.lower()]

        data = []
        for a in activities:
            data.append({
                "activity_id": a.activity_id,
                "course_id": a.course_id,
                "course_name": a.course_name,
                "activity_type": a.activity_type.value,
                "title": a.title,
                "description": a.description,
                "posted_date": a.posted_date.isoformat() if a.posted_date else None,
                "deadline": a.deadline.isoformat() if a.deadline else None,
                "remaining_str": a.remaining_str(),
                "remaining_hours": a.remaining_hours,
                "is_overdue": a.is_overdue,
                "is_fyp": a.is_fyp,
                "submission_status": a.submission_status.value,
                "marks": a.marks,
                "attachment_url": a.attachment_url,
                "attachment_name": a.attachment_name,
                "local_file_path": a.local_file_path,
                "ai_summary": a.ai_summary,
                "portal_url": a.portal_url,
                "priority": a.priority.value,
                "reminders_sent": a.reminders_sent
            })
        return data

    @app.get("/api/download-file")
    async def download_file(path: str):
        file_path = Path(path).resolve()
        downloads_base = (Path(__file__).resolve().parent.parent / "downloads").resolve()
        try:
            file_path.relative_to(downloads_base)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(file_path, filename=file_path.name)

    @app.get("/api/notifications")
    async def get_notifications(limit: int = 50):
        return database.get_recent_notifications(limit)

    @app.get("/api/settings")
    async def get_settings():
        return database.get_all_settings()

    class SettingsUpdate(BaseModel):
        settings: Dict[str, str]

    @app.post("/api/settings")
    async def update_settings(payload: SettingsUpdate):
        for k, v in payload.settings.items():
            database.set_setting(k, str(v))
        return {"status": "success", "message": "Settings updated."}

    @app.get("/api/gpa/projection")
    async def get_gpa_projection():
        from engine.gpa_engine import GPAEngine
        profile = database.get_student_profile()
        current_cgpa = float(profile.get("current_cgpa", 3.20))
        completed_credits = int(profile.get("completed_credits", 100))
        target_gpa = float(profile.get("target_gpa", 3.50))

        courses = database.get_all_courses()
        sem_courses = [{"course_name": c.name, "credits": 3, "expected_grade": "A"} for c in courses]
        if not sem_courses:
            sem_courses = [
                {"course_name": "FYP - Design Project", "credits": 3, "expected_grade": "A"},
                {"course_name": "Software Architecture", "credits": 3, "expected_grade": "A"},
                {"course_name": "Course 3", "credits": 3, "expected_grade": "A-"},
                {"course_name": "Course 4", "credits": 3, "expected_grade": "B+"}
            ]

        projection = GPAEngine.project_cgpa(current_cgpa, completed_credits, sem_courses)
        
        # Course advising
        course_status = [{"name": c.name, "attendance_pct": c.attendance_pct, "is_fyp": c.is_fyp} for c in courses]
        advising = GPAEngine.get_strategic_advising(course_status)

        return {
            "profile": {
                "current_cgpa": current_cgpa,
                "completed_credits": completed_credits,
                "target_gpa": target_gpa
            },
            "projection": projection,
            "advising": advising,
            "scale": [
                {"grade": "A", "min_pct": 85, "gpa": 4.00},
                {"grade": "A-", "min_pct": 80, "gpa": 3.66},
                {"grade": "B+", "min_pct": 75, "gpa": 3.33},
                {"grade": "B", "min_pct": 71, "gpa": 3.00},
                {"grade": "B-", "min_pct": 68, "gpa": 2.66},
                {"grade": "C+", "min_pct": 64, "gpa": 2.33},
                {"grade": "C", "min_pct": 60, "gpa": 2.00},
            ]
        }

    class FinalCalcRequest(BaseModel):
        sessional_obtained: float
        sessional_total: float
        final_exam_total: float = 40.0
        target_grade: str = "A"

    @app.post("/api/gpa/calculate-final")
    async def calculate_final_needed(req: FinalCalcRequest):
        from engine.gpa_engine import GPAEngine
        return GPAEngine.calculate_marks_needed_in_final(
            req.sessional_obtained, req.sessional_total, req.final_exam_total, req.target_grade
        )

    class AIQueryRequest(BaseModel):
        query: str

    @app.post("/api/ai/chat")
    async def ai_academic_chat(req: AIQueryRequest):
        from engine.ai_agent import AcademicAIAgent
        agent = monitor_agent.ai_agent if (monitor_agent and hasattr(monitor_agent, "ai_agent")) else AcademicAIAgent()
        
        courses = database.get_all_courses()
        all_activities = database.get_all_activities()
        pending = [a for a in all_activities if a.submission_status not in (SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED) and a.activity_type in (ActivityType.ASSIGNMENT, ActivityType.PROJECT)]
        profile = database.get_student_profile()
        
        # Downloaded files list
        downloads_dir = Path(__file__).resolve().parent.parent / "downloads"
        downloaded_files = [str(f.name) for f in downloads_dir.glob("**/*") if f.is_file()]

        context = {
            "courses": courses,
            "all_activities": all_activities,
            "pending_activities": pending,
            "current_cgpa": profile.get("current_cgpa", 3.20),
            "completed_credits": profile.get("completed_credits", 100),
            "downloaded_files": downloaded_files
        }

        answer = agent.answer_query(req.query, context)
        return {"query": req.query, "response": answer}

    @app.post("/api/trigger-check")
    async def trigger_check(background_tasks: BackgroundTasks):
        if monitor_agent:
            background_tasks.add_task(monitor_agent.run_check_cycle)
            return {"status": "started", "message": "Portal check cycle initiated in background."}
        return {"status": "error", "message": "Monitor agent not attached."}

    class TestMessageRequest(BaseModel):
        phone_number: str
        message: Optional[str] = "🔔 Test notification from your ODOCUST Academic Agent!"

    @app.post("/api/send-test-whatsapp")
    async def send_test_whatsapp(req: TestMessageRequest):
        if not monitor_agent or not monitor_agent.notifier:
            raise HTTPException(status_code=500, detail="Notifier not configured.")
        
        success = monitor_agent.notifier.send_message(req.phone_number, req.message)
        if success:
            return {"status": "success", "message": f"Test message sent to {req.phone_number}"}
        else:
            raise HTTPException(status_code=400, detail="Failed to send message. Check WhatsApp provider settings.")

    # ---------------------------------------------------------------
    # SESSIONAL MARGIN GUARD — /api/margin/*
    # ---------------------------------------------------------------

    class MarkEntryRequest(BaseModel):
        course_id: str
        course_name: str
        component: str
        component_type: str = "other"   # quiz | assignment | midterm | lab | other
        obtained: float
        total: float

    @app.post("/api/margin/add-mark")
    async def add_mark(req: MarkEntryRequest):
        """Add or update a component mark for a course."""
        database.upsert_course_mark(
            req.course_id, req.course_name,
            req.component, req.component_type,
            req.obtained, req.total
        )
        return {"status": "success", "message": f"Mark saved: {req.component} ({req.obtained}/{req.total})"}

    @app.get("/api/margin/report")
    async def get_margin_report():
        """Return per-course sessional margin guard report."""
        from engine.margin_guard import MarginGuard
        all_marks = database.get_all_course_marks()

        # Group by course
        course_map: Dict[str, list] = {}
        for m in all_marks:
            cid = m["course_id"]
            if cid not in course_map:
                course_map[cid] = []
            course_map[cid].append(m)

        report = []
        for cid, marks in course_map.items():
            from engine.margin_guard import CourseMarksEntry
            entries = [
                CourseMarksEntry(
                    course_id=m["course_id"],
                    course_name=m["course_name"],
                    component=m["component"],
                    obtained=m["obtained"],
                    total=m["total"],
                    component_type=m["component_type"],
                    entered_at=m["entered_at"]
                )
                for m in marks
            ]
            margin = MarginGuard.compute_margin(entries)
            report.append({
                "course_id": cid,
                "course_name": marks[0]["course_name"],
                "components": [
                    {
                        "component": m["component"],
                        "component_type": m["component_type"],
                        "obtained": m["obtained"],
                        "total": m["total"],
                        "pct": round(m["obtained"] / m["total"] * 100, 1) if m["total"] > 0 else 0,
                        "entered_at": m["entered_at"]
                    }
                    for m in marks
                ],
                **margin
            })

        return {"courses": report}

    @app.delete("/api/margin/delete-mark/{mark_id}")
    async def delete_mark(mark_id: int):
        database.delete_course_mark(mark_id)
        return {"status": "success", "message": f"Mark entry {mark_id} deleted."}

    @app.get("/api/margin/marks/{course_id}")
    async def get_marks_for_course(course_id: str):
        return database.get_course_marks(course_id)

    # ---------------------------------------------------------------
    # PRE-SUBMISSION RUBRIC AUDITOR — /api/rubric/*
    # ---------------------------------------------------------------

    class RubricAuditRequest(BaseModel):
        draft_file_path: str
        activity_id: str = ""
        course_name: str = ""
        assignment_title: str = ""
        assignment_description: str = ""

    @app.post("/api/rubric/audit")
    async def run_rubric_audit(req: RubricAuditRequest):
        """Trigger a rubric audit on a draft file path."""
        from engine.rubric_auditor import RubricAuditor
        auditor = RubricAuditor()

        # If activity_id provided, grab description + local file from DB
        assignment_description = req.assignment_description
        assignment_file_path = ""
        if req.activity_id:
            activity = database.get_activity(req.activity_id)
            if activity:
                assignment_description = assignment_description or activity.description
                assignment_file_path = activity.local_file_path

        result = auditor.audit_draft(
            draft_path=req.draft_file_path,
            assignment_description=assignment_description,
            assignment_file_path=assignment_file_path,
            course_name=req.course_name,
            assignment_title=req.assignment_title
        )

        # Persist to DB
        row_id = database.save_rubric_audit(
            result,
            activity_id=req.activity_id,
            course_name=req.course_name,
            assignment_title=req.assignment_title
        )
        result["audit_id"] = row_id
        return result

    @app.get("/api/rubric/history")
    async def get_audit_history(limit: int = 20):
        """Get recent rubric audit history."""
        return database.get_recent_audits(limit)

    @app.get("/api/rubric/scan-submissions")
    async def scan_submissions_folder():
        """Scan the submissions/ folder for any draft files and audit all."""
        from engine.rubric_auditor import RubricAuditor
        auditor = RubricAuditor()
        results = auditor.scan_submissions_folder()
        saved = []
        for r in results:
            row_id = database.save_rubric_audit(r)
            r["audit_id"] = row_id
            saved.append(r)
        return {"audits": saved, "count": len(saved)}

    return app



