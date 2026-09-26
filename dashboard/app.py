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

    return app
