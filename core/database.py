import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from core.models import AcademicActivity, Course, ActivityType, SubmissionStatus, PriorityLevel, NotificationRecord

class Database:
    def __init__(self, db_path: str = "odocust_monitor.db"):
        self.db_path = db_path
        self._init_db()

    import contextlib

    @contextlib.contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Courses table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                course_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                code TEXT,
                instructor TEXT,
                url TEXT,
                attendance_pct REAL DEFAULT 100.0,
                last_synced TEXT
            );
            """)

            # Academic Activities table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                activity_id TEXT PRIMARY KEY,
                course_id TEXT NOT NULL,
                course_name TEXT NOT NULL,
                activity_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                posted_date TEXT,
                deadline TEXT,
                submission_status TEXT NOT NULL,
                marks TEXT,
                attachment_url TEXT,
                attachment_name TEXT,
                local_file_path TEXT DEFAULT '',
                portal_url TEXT,
                priority TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_checked_at TEXT NOT NULL,
                first_notified_at TEXT,
                reminders_sent TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (course_id) REFERENCES courses (course_id) ON DELETE CASCADE
            );
            """)

            # Migrations for existing databases
            cursor.execute("PRAGMA table_info(courses);")
            course_cols = [c[1] for c in cursor.fetchall()]
            if "attendance_pct" not in course_cols:
                cursor.execute("ALTER TABLE courses ADD COLUMN attendance_pct REAL DEFAULT 100.0;")

            cursor.execute("PRAGMA table_info(activities);")
            act_cols = [c[1] for c in cursor.fetchall()]
            if "local_file_path" not in act_cols:
                cursor.execute("ALTER TABLE activities ADD COLUMN local_file_path TEXT DEFAULT '';")
            if "ai_summary" not in act_cols:
                cursor.execute("ALTER TABLE activities ADD COLUMN ai_summary TEXT DEFAULT '';")

            # Student Academic Profile
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_profile (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """)

            # Notifications Log table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_id TEXT,
                notification_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                message_text TEXT NOT NULL,
                status TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                error_message TEXT
            );
            """)

            # System Settings table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """)

            # Default settings if not present
            defaults = {
                "check_interval_minutes": "15",
                "reminder_hours": "[72, 48, 24, 12, 6, 3, 1]",
                "whatsapp_enabled": "true",
                "whatsapp_provider": "console_log",  # 'twilio', 'greenapi', 'callmebot', 'meta', 'console_log'
                "whatsapp_to_number": "",
                "daily_summary_enabled": "true",
                "daily_summary_time": "08:00",
                "last_daily_summary_date": "",
                "portal_status": "OK",
                "portal_last_error": "",
                "portal_last_checked": ""
            }
            for k, v in defaults.items():
                cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);", (k, v))
                
            conn.commit()

    # --- COURSE METHODS ---
    def upsert_course(self, course: Course) -> Tuple[Course, Optional[float], float]:
        """
        Inserts or updates a course and tracks changes in attendance percentage.
        Returns: (course, old_attendance, new_attendance)
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT attendance_pct FROM courses WHERE course_id = ?", (course.course_id,))
            existing = cursor.fetchone()
            old_attendance = existing["attendance_pct"] if existing and existing["attendance_pct"] is not None else None
            new_attendance = course.attendance_pct

            conn.execute("""
            INSERT INTO courses (course_id, name, code, instructor, url, attendance_pct, last_synced)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(course_id) DO UPDATE SET
                name=excluded.name,
                code=excluded.code,
                instructor=excluded.instructor,
                url=excluded.url,
                attendance_pct=excluded.attendance_pct,
                last_synced=excluded.last_synced;
            """, (
                course.course_id,
                course.name,
                course.code,
                course.instructor,
                course.url,
                course.attendance_pct,
                course.last_synced.isoformat() if course.last_synced else None
            ))
            conn.commit()
            return course, old_attendance, new_attendance

    def get_all_courses(self) -> List[Course]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM courses ORDER BY name ASC")
            courses = []
            for row in cursor.fetchall():
                att = 100.0
                try:
                    if "attendance_pct" in row.keys() and row["attendance_pct"] is not None:
                        att = float(row["attendance_pct"])
                except Exception:
                    att = 100.0

                courses.append(Course(
                    course_id=row["course_id"],
                    name=row["name"],
                    code=row["code"] or "",
                    instructor=row["instructor"] or "",
                    url=row["url"] or "",
                    attendance_pct=att,
                    last_synced=datetime.fromisoformat(row["last_synced"]) if row["last_synced"] else None
                ))
            return courses

    # --- ACTIVITY METHODS ---
    def upsert_activity(self, activity: AcademicActivity) -> Tuple[AcademicActivity, bool, Dict[str, Any]]:
        """
        Inserts or updates an activity.
        Returns: (activity, is_new, changes_dict)
        changes_dict tracks changes in deadline, submission_status, or description.
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM activities WHERE activity_id = ?", (activity.activity_id,))
            existing = cursor.fetchone()
            
            changes = {}
            is_new = False
            
            if existing is None:
                is_new = True
                conn.execute("""
                INSERT INTO activities (
                    activity_id, course_id, course_name, activity_type, title, description,
                    posted_date, deadline, submission_status, marks, attachment_url,
                    attachment_name, local_file_path, ai_summary, portal_url, priority, first_seen_at, last_checked_at,
                    first_notified_at, reminders_sent
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    activity.activity_id,
                    activity.course_id,
                    activity.course_name,
                    activity.activity_type.value,
                    activity.title,
                    activity.description,
                    activity.posted_date.isoformat() if activity.posted_date else None,
                    activity.deadline.isoformat() if activity.deadline else None,
                    activity.submission_status.value,
                    activity.marks,
                    activity.attachment_url,
                    activity.attachment_name,
                    activity.local_file_path,
                    activity.ai_summary,
                    activity.portal_url,
                    activity.priority.value,
                    activity.first_seen_at.isoformat(),
                    activity.last_checked_at.isoformat(),
                    activity.first_notified_at.isoformat() if activity.first_notified_at else None,
                    json.dumps(activity.reminders_sent)
                ))
            else:
                # Compare to detect changes
                old_deadline_str = existing["deadline"]
                new_deadline_str = activity.deadline.isoformat() if activity.deadline else None
                if old_deadline_str != new_deadline_str:
                    changes["deadline"] = {
                        "old": datetime.fromisoformat(old_deadline_str) if old_deadline_str else None,
                        "new": activity.deadline
                    }
                    
                old_status = existing["submission_status"]
                new_status = activity.submission_status.value
                if old_status != new_status:
                    changes["submission_status"] = {
                        "old": old_status,
                        "new": new_status
                    }

                # Maintain notification history and local file path from DB if not overwritten
                activity.first_notified_at = datetime.fromisoformat(existing["first_notified_at"]) if existing["first_notified_at"] else None
                activity.reminders_sent = json.loads(existing["reminders_sent"] or "[]")
                activity.first_seen_at = datetime.fromisoformat(existing["first_seen_at"])
                
                try:
                    if not activity.local_file_path and "local_file_path" in existing.keys() and existing["local_file_path"]:
                        activity.local_file_path = existing["local_file_path"]
                    if not activity.ai_summary and "ai_summary" in existing.keys() and existing["ai_summary"]:
                        activity.ai_summary = existing["ai_summary"]
                except Exception:
                    pass

                conn.execute("""
                UPDATE activities SET
                    course_name = ?,
                    title = ?,
                    description = ?,
                    deadline = ?,
                    submission_status = ?,
                    marks = ?,
                    attachment_url = ?,
                    attachment_name = ?,
                    local_file_path = ?,
                    ai_summary = ?,
                    portal_url = ?,
                    priority = ?,
                    last_checked_at = ?
                WHERE activity_id = ?;
                """, (
                    activity.course_name,
                    activity.title,
                    activity.description,
                    activity.deadline.isoformat() if activity.deadline else None,
                    activity.submission_status.value,
                    activity.marks,
                    activity.attachment_url,
                    activity.attachment_name,
                    activity.local_file_path,
                    activity.ai_summary,
                    activity.portal_url,
                    activity.priority.value,
                    activity.last_checked_at.isoformat(),
                    activity.activity_id
                ))
                
            conn.commit()
            return activity, is_new, changes

    def update_activity_local_file(self, activity_id: str, local_path: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE activities SET local_file_path = ? WHERE activity_id = ?", (local_path, activity_id))
            conn.commit()

    def update_activity_ai_summary(self, activity_id: str, ai_summary: str):
        with self._get_connection() as conn:
            conn.execute("UPDATE activities SET ai_summary = ? WHERE activity_id = ?", (ai_summary, activity_id))
            conn.commit()

    def get_student_profile(self) -> Dict[str, str]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM student_profile")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    def set_student_profile(self, key: str, value: str):
        with self._get_connection() as conn:
            conn.execute("INSERT OR REPLACE INTO student_profile (key, value) VALUES (?, ?)", (key, value))
            conn.commit()

    def get_all_activities(self) -> List[AcademicActivity]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM activities ORDER BY deadline ASC, first_seen_at DESC")
            return [self._row_to_activity(row) for row in cursor.fetchall()]

    def get_activity(self, activity_id: str) -> Optional[AcademicActivity]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM activities WHERE activity_id = ?", (activity_id,))
            row = cursor.fetchone()
            return self._row_to_activity(row) if row else None

    def mark_first_notified(self, activity_id: str, notified_at: Optional[datetime] = None):
        notified_at = notified_at or datetime.now()
        with self._get_connection() as conn:
            conn.execute("UPDATE activities SET first_notified_at = ? WHERE activity_id = ?", 
                         (notified_at.isoformat(), activity_id))
            conn.commit()

    def record_reminder_sent(self, activity_id: str, hour_interval: int):
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT reminders_sent FROM activities WHERE activity_id = ?", (activity_id,))
            row = cursor.fetchone()
            if row:
                reminders = json.loads(row["reminders_sent"] or "[]")
                if hour_interval not in reminders:
                    reminders.append(hour_interval)
                    conn.execute("UPDATE activities SET reminders_sent = ? WHERE activity_id = ?",
                                 (json.dumps(reminders), activity_id))
                    conn.commit()

    def _row_to_activity(self, row: sqlite3.Row) -> AcademicActivity:
        local_path = ""
        try:
            if "local_file_path" in row.keys() and row["local_file_path"]:
                local_path = row["local_file_path"]
        except Exception:
            local_path = ""

        ai_summary = ""
        try:
            if "ai_summary" in row.keys() and row["ai_summary"]:
                ai_summary = row["ai_summary"]
        except Exception:
            ai_summary = ""

        return AcademicActivity(
            activity_id=row["activity_id"],
            course_id=row["course_id"],
            course_name=row["course_name"],
            activity_type=ActivityType(row["activity_type"]),
            title=row["title"],
            description=row["description"] or "",
            posted_date=datetime.fromisoformat(row["posted_date"]) if row["posted_date"] else None,
            deadline=datetime.fromisoformat(row["deadline"]) if row["deadline"] else None,
            submission_status=SubmissionStatus(row["submission_status"]),
            marks=row["marks"] or "",
            attachment_url=row["attachment_url"] or "",
            attachment_name=row["attachment_name"] or "",
            local_file_path=local_path,
            ai_summary=ai_summary,
            portal_url=row["portal_url"] or "",
            priority=PriorityLevel(row["priority"]),
            first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
            last_checked_at=datetime.fromisoformat(row["last_checked_at"]),
            first_notified_at=datetime.fromisoformat(row["first_notified_at"]) if row["first_notified_at"] else None,
            reminders_sent=json.loads(row["reminders_sent"] or "[]")
        )

    # --- NOTIFICATION LOGS ---
    def log_notification(self, notif: NotificationRecord):
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO notifications_log (
                activity_id, notification_type, priority, message_text, status, sent_at, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (
                notif.activity_id,
                notif.notification_type,
                notif.priority.value,
                notif.message_text,
                notif.status,
                (notif.sent_at or datetime.now()).isoformat(),
                notif.error_message
            ))
            conn.commit()

    def get_recent_notifications(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM notifications_log ORDER BY id DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    # --- SETTINGS METHODS ---
    def get_setting(self, key: str, default: str = "") -> str:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value;
            """, (key, value))
            conn.commit()

    def get_all_settings(self) -> Dict[str, str]:
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT key, value FROM settings")
            return {row["key"]: row["value"] for row in cursor.fetchall()}

    # --- SUMMARY METRICS ---
    def get_dashboard_summary(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            total_courses = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
            total_activities = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
            
            # Pending / not submitted
            pending_assignments = conn.execute("""
            SELECT COUNT(*) FROM activities 
            WHERE activity_type IN ('Assignment', 'Project') 
              AND submission_status NOT IN ('Submitted', 'Graded')
              AND (deadline IS NULL OR deadline >= datetime('now', 'localtime'))
            """).fetchone()[0]
            
            submitted_count = conn.execute("""
            SELECT COUNT(*) FROM activities 
            WHERE submission_status IN ('Submitted', 'Graded')
            """).fetchone()[0]
            
            upcoming_deadlines_24h = conn.execute("""
            SELECT COUNT(*) FROM activities 
            WHERE deadline IS NOT NULL 
              AND deadline >= datetime('now', 'localtime')
              AND deadline <= datetime('now', 'localtime', '+24 hours')
              AND submission_status NOT IN ('Submitted', 'Graded')
            """).fetchone()[0]

            overdue_count = conn.execute("""
            SELECT COUNT(*) FROM activities 
            WHERE deadline IS NOT NULL 
              AND deadline < datetime('now', 'localtime')
              AND submission_status NOT IN ('Submitted', 'Graded')
            """).fetchone()[0]

            return {
                "total_courses": total_courses,
                "total_activities": total_activities,
                "pending_assignments": pending_assignments,
                "submitted_count": submitted_count,
                "upcoming_24h": upcoming_deadlines_24h,
                "overdue_count": overdue_count
            }
