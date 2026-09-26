import os
import logging
import time
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from core.auth import OdoCustAuth, AuthenticationError
from core.extractor import OdoCustExtractor
from core.database import Database
from core.models import AcademicActivity, Course, NotificationRecord, PriorityLevel, SubmissionStatus
from engine.priority import PriorityClassifier
from engine.deadline import DeadlineEngine
from engine.downloader import DocumentDownloader
from engine.ai_agent import AcademicAIAgent
from notifier.formatter import NotificationFormatter
from notifier.whatsapp import BaseWhatsAppNotifier

logger = logging.getLogger("odocust.monitor")

class AcademicMonitorAgent:
    def __init__(
        self,
        auth: OdoCustAuth,
        db: Database,
        extractor: OdoCustExtractor,
        notifier: BaseWhatsAppNotifier,
        whatsapp_to_number: str = "",
        dashboard_url: str = "http://127.0.0.1:8080"
    ):
        self.auth = auth
        self.db = db
        self.extractor = extractor
        self.notifier = notifier
        self.whatsapp_to_number = whatsapp_to_number
        self.dashboard_url = dashboard_url
        self.deadline_engine = DeadlineEngine(self.db)
        self.downloader = DocumentDownloader(base_download_dir="downloads")
        self.ai_agent = AcademicAIAgent()

    def run_check_cycle(self) -> Dict[str, Any]:
        """
        Executes a complete monitoring cycle:
        1. Authenticates & checks portal health
        2. Discovers courses from dashboard and tracks attendance
        3. Scrapes announcements, submissions, assessments, and course materials
        4. Automatically downloads new documents/PDFs/files into subject folders
        5. Detects new/changed activities and sends WhatsApp alerts (FYP = HIGHEST PRIORITY)
        6. Evaluates approaching deadlines and sends smart reminders
        7. Checks for daily academic summary
        """
        cycle_start = datetime.now()
        logger.info(f"Starting ODOCUST monitor cycle at {cycle_start.strftime('%Y-%m-%d %H:%M:%S')}")
        
        cycle_stats = {
            "status": "SUCCESS",
            "courses_found": 0,
            "activities_scanned": 0,
            "new_activities": 0,
            "fyp_activities": 0,
            "files_downloaded": 0,
            "attendance_alerts": 0,
            "reminders_sent": 0,
            "changes_detected": 0,
            "error": None
        }

        # Step 1: Authenticate
        try:
            session = self.auth.get_authenticated_session()
            self.db.set_setting("portal_status", "OK")
            self.db.set_setting("portal_last_checked", cycle_start.isoformat())
            self.db.set_setting("portal_last_error", "")
        except AuthenticationError as e:
            err_msg = str(e)
            logger.error(f"Authentication failure: {err_msg}")
            self.db.set_setting("portal_status", "ERROR")
            self.db.set_setting("portal_last_error", err_msg)
            
            # Send alert to user if status wasn't already in error state
            alert_msg = NotificationFormatter.format_system_alert(err_msg, self.auth.base_url)
            self._dispatch_notification(None, "SYSTEM_ALERT", PriorityLevel.CRITICAL, alert_msg)
            cycle_stats["status"] = "AUTH_ERROR"
            cycle_stats["error"] = err_msg
            return cycle_stats
        except Exception as e:
            err_msg = f"Unexpected connection error: {e}"
            logger.error(err_msg)
            self.db.set_setting("portal_status", "ERROR")
            self.db.set_setting("portal_last_error", err_msg)
            cycle_stats["status"] = "NETWORK_ERROR"
            cycle_stats["error"] = err_msg
            return cycle_stats

        # Step 2: Fetch Dashboard & Discover Enrolled Courses
        dashboard_url = f"{self.auth.base_url}/student/dashboard"
        try:
            dash_res = session.get(dashboard_url, timeout=20, verify=False)
            courses = self.extractor.parse_dashboard_courses(dash_res.text)
        except Exception as e:
            logger.error(f"Failed to fetch student dashboard: {e}")
            courses = []

        # If dashboard didn't list courses (or only 1 active page), load known courses from database
        if not courses:
            known_courses = self.db.get_all_courses()
            if known_courses:
                courses = known_courses
                logger.info(f"Using {len(courses)} previously known courses from database.")
        else:
            for c in courses:
                saved_course, old_att, new_att = self.db.upsert_course(c)
                # Check for attendance drops or dangerously low attendance
                if old_att is not None and new_att < old_att:
                    cycle_stats["attendance_alerts"] += 1
                    logger.warning(f"📉 Attendance drop detected for {c.name}: {old_att:.1f}% -> {new_att:.1f}%")
                    p = PriorityLevel.CRITICAL if new_att < 75.0 else PriorityLevel.HIGH
                    att_msg = NotificationFormatter.format_attendance_alert(c, old_att, new_att)
                    self._dispatch_notification(None, "ATTENDANCE_DROP", p, att_msg)
                elif old_att is None and new_att < 75.0:
                    cycle_stats["attendance_alerts"] += 1
                    p = PriorityLevel.CRITICAL
                    att_msg = NotificationFormatter.format_attendance_alert(c, None, new_att)
                    self._dispatch_notification(None, "ATTENDANCE_LOW", p, att_msg)

        # Prioritize FYP to be scanned first
        courses.sort(key=lambda c: 0 if c.is_fyp else 1)

        cycle_stats["courses_found"] = len(courses)
        logger.info(f"Monitoring {len(courses)} active course(s). FYP prioritized first.")

        # Step 3: Scan each course for activities
        all_new_items: List[AcademicActivity] = []

        for course in courses:
            scanned = self._scan_course(session, course)
            cycle_stats["activities_scanned"] += len(scanned)

            for activity in scanned:
                # Automatic document/file download
                if activity.attachment_url:
                    local_path = self.downloader.download_activity_attachment(session, activity)
                    if local_path:
                        activity.local_file_path = local_path
                        cycle_stats["files_downloaded"] += 1

                # AI Document Analysis & 2-3 Line Summarization
                if not activity.ai_summary:
                    try:
                        summary = self.ai_agent.analyze_document_and_summarize(activity)
                        if summary:
                            activity.ai_summary = summary
                    except Exception as e:
                        logger.warning(f"AI summarization skipped for {activity.title}: {e}")

                # Upsert into database and check for diffs
                saved_activity, is_new, changes = self.db.upsert_activity(activity)

                # Classify Priority (FYP is automatically CRITICAL)
                saved_activity.priority = PriorityClassifier.classify(saved_activity, changes)

                if is_new:
                    cycle_stats["new_activities"] += 1
                    all_new_items.append(saved_activity)
                    if saved_activity.is_fyp:
                        cycle_stats["fyp_activities"] += 1
                        logger.info(f"🚨🎓 NEW FYP ACTIVITY: {saved_activity.title} ({course.name})")
                    else:
                        logger.info(f"✨ NEW ACTIVITY: [{saved_activity.activity_type.value}] {saved_activity.title} ({course.name})")
                    
                    # Format and send immediate WhatsApp/Telegram alert
                    msg = NotificationFormatter.format_new_activity(saved_activity)
                    self._dispatch_notification(saved_activity.activity_id, "NEW", saved_activity.priority, msg)
                    self.db.mark_first_notified(saved_activity.activity_id)

                elif changes:
                    cycle_stats["changes_detected"] += 1
                    logger.info(f"🔄 CHANGES in {saved_activity.title}: {changes}")
                    
                    if "submission_status" in changes:
                        old_s = changes["submission_status"]["old"]
                        new_s = changes["submission_status"]["new"]
                        msg = NotificationFormatter.format_status_change(saved_activity, old_s, new_s)
                        self._dispatch_notification(saved_activity.activity_id, "STATUS_CHANGE", PriorityLevel.HIGH, msg)

                    if "deadline" in changes:
                        # Re-classify priority with critical urgency if deadline moved closer
                        msg = f"⏳ *Deadline Updated*\n\nCourse: {saved_activity.course_name}\nTask: {saved_activity.title}\nNew Deadline: {saved_activity.deadline.strftime('%d %B, %I:%M %p') if saved_activity.deadline else 'None'}\nRemaining: {saved_activity.remaining_str()}"
                        self._dispatch_notification(saved_activity.activity_id, "DEADLINE_CHANGE", PriorityLevel.CRITICAL, msg)

        # Download any files for previously saved activities missing local files & generate AI summaries
        try:
            for past_act in self.db.get_all_activities():
                if past_act.attachment_url and (not past_act.local_file_path or not os.path.exists(past_act.local_file_path)):
                    dl_path = self.downloader.download_activity_attachment(session, past_act)
                    if dl_path:
                        past_act.local_file_path = dl_path
                        self.db.update_activity_local_file(past_act.activity_id, dl_path)
                        cycle_stats["files_downloaded"] += 1

                if not past_act.ai_summary and (past_act.local_file_path or past_act.description):
                    try:
                        summary = self.ai_agent.analyze_document_and_summarize(past_act)
                        if summary:
                            past_act.ai_summary = summary
                            self.db.update_activity_ai_summary(past_act.activity_id, summary)
                    except Exception as e:
                        logger.warning(f"Error generating AI summary for past activity: {e}")
        except Exception as e:
            logger.warning(f"Error checking pending attachment downloads or AI summaries: {e}")

        # Step 4: Evaluate Approaching Deadlines & Send Scheduled Reminders
        due_reminders = self.deadline_engine.evaluate_reminders()
        for activity, threshold in due_reminders:
            cycle_stats["reminders_sent"] += 1
            logger.info(f"⏰ REMINDER ({threshold}h): {activity.title} ({activity.course_name})")
            
            reminder_msg = NotificationFormatter.format_deadline_reminder(activity, threshold)
            priority = PriorityLevel.CRITICAL if threshold <= 24 else PriorityLevel.HIGH
            
            dispatched = self._dispatch_notification(activity.activity_id, "REMINDER", priority, reminder_msg)
            if dispatched:
                self.db.record_reminder_sent(activity.activity_id, threshold)

        # Step 5: Check Daily Academic Summary Trigger
        self._check_daily_summary(all_new_items)

        logger.info(f"Cycle completed in {(datetime.now() - cycle_start).total_seconds():.2f}s. Stats: {cycle_stats}")
        return cycle_stats

    def _scan_course(self, session, course: Course) -> List[AcademicActivity]:
        """
        Scans all tabs for an individual course:
        - Announcements / News (/student/course/info/<hash>)
        - Submissions (/student/course/submission/<hash>)
        - Assessments (/student/course/assessment/<hash>)
        """
        logger.info(f"Scanning course: {course.name} ({course.code})")
        activities: List[AcademicActivity] = []

        # 1. Announcements / News
        info_url = f"{self.auth.base_url}/student/course/info/{course.course_id}"
        try:
            res = session.get(info_url, timeout=30, verify=False)
            if res.status_code == 200:
                announcements = self.extractor.parse_announcements(res.text, course)
                activities.extend(announcements)
        except Exception as e:
            logger.warning(f"Error fetching info for course {course.name}: {e}")

        # 2. Submissions (Assignments / Projects)
        sub_url = f"{self.auth.base_url}/student/course/submission/{course.course_id}"
        try:
            res = session.get(sub_url, timeout=30, verify=False)
            if res.status_code == 200:
                submissions = self.extractor.parse_submissions(res.text, course)
                activities.extend(submissions)
        except Exception as e:
            logger.warning(f"Error fetching submissions for course {course.name}: {e}")

        # 3. Assessments (Quizzes / Exams)
        assess_url = f"{self.auth.base_url}/student/course/assessment/{course.course_id}"
        try:
            res = session.get(assess_url, timeout=30, verify=False)
            if res.status_code == 200:
                assessments = self.extractor.parse_assessments(res.text, course)
                activities.extend(assessments)
        except Exception as e:
            logger.warning(f"Error fetching assessments for course {course.name}: {e}")

        # 4. Course Materials / PDFs
        material_url = f"{self.auth.base_url}/student/course/material/{course.course_id}"
        try:
            res = session.get(material_url, timeout=30, verify=False)
            if res.status_code == 200:
                materials = self.extractor.parse_materials(res.text, course)
                activities.extend(materials)
        except Exception as e:
            logger.warning(f"Error fetching materials for course {course.name}: {e}")

        return activities

    def _dispatch_notification(
        self,
        activity_id: Optional[str],
        notif_type: str,
        priority: PriorityLevel,
        message: str
    ) -> bool:
        """
        Dispatches notification via WhatsApp and logs to persistent database.
        """
        to_number = self.whatsapp_to_number or self.db.get_setting("whatsapp_to_number")
        success = self.notifier.send_message(to_number, message)
        
        notif_record = NotificationRecord(
            activity_id=activity_id,
            notification_type=notif_type,
            priority=priority,
            message_text=message,
            status="SENT" if success else "FAILED",
            sent_at=datetime.now(),
            error_message="" if success else "WhatsApp/Telegram provider failed to dispatch"
        )
        self.db.log_notification(notif_record)
        time.sleep(1.0)
        return success

    def _check_daily_summary(self, new_items: List[AcademicActivity]):
        """
        Sends the daily summary once per day at or after the configured DAILY_SUMMARY_TIME.
        """
        daily_enabled = self.db.get_setting("daily_summary_enabled", "true").lower() == "true"
        if not daily_enabled:
            return

        target_time_str = self.db.get_setting("daily_summary_time", "08:00")
        today_date_str = date.today().isoformat()
        last_sent_date = self.db.get_setting("last_daily_summary_date", "")

        if last_sent_date == today_date_str:
            return  # Already sent today

        now_time = datetime.now().time()
        try:
            target_hour, target_min = [int(p) for p in target_time_str.split(":")]
        except ValueError:
            target_hour, target_min = 8, 0

        # If current time is past the target summary time, send it!
        if (now_time.hour > target_hour) or (now_time.hour == target_hour and now_time.minute >= target_min):
            all_activities = self.db.get_all_activities()
            upcoming = [a for a in all_activities if a.deadline and 0 <= (a.remaining_hours or 0) <= 72 and a.submission_status not in (SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED)]
            unsubmitted = [a for a in all_activities if a.activity_type in (ActivityType.ASSIGNMENT, ActivityType.PROJECT) and a.submission_status not in (SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED)]
            submitted = [a for a in all_activities if a.submission_status in (SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED)]

            summary_msg = NotificationFormatter.format_daily_summary(
                new_items=new_items,
                upcoming_items=upcoming,
                unsubmitted_items=unsubmitted,
                submitted_items=submitted,
                dashboard_url=self.dashboard_url
            )

            dispatched = self._dispatch_notification(None, "DAILY_SUMMARY", PriorityLevel.NORMAL, summary_msg)
            if dispatched:
                self.db.set_setting("last_daily_summary_date", today_date_str)
                logger.info("Daily academic summary dispatched successfully.")
