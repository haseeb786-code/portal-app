import unittest
from datetime import datetime, timedelta
import os

from core.models import Course, AcademicActivity, ActivityType, SubmissionStatus, PriorityLevel, NotificationRecord
from core.database import Database
from core.extractor import OdoCustExtractor
from engine.priority import PriorityClassifier
from engine.deadline import DeadlineEngine
from notifier.formatter import NotificationFormatter
from notifier.whatsapp import ConsoleLogNotifier

class TestAcademicMonitor(unittest.TestCase):
    def setUp(self):
        import uuid
        self.test_db_path = f"test_odocust_{uuid.uuid4().hex[:8]}.db"
        self.db = Database(self.test_db_path)
        self.extractor = OdoCustExtractor("https://odoo.cust.edu.pk")

    def tearDown(self):
        import gc
        gc.collect()
        try:
            if os.path.exists(self.test_db_path):
                os.remove(self.test_db_path)
        except Exception:
            pass

    def test_database_and_deduplication(self):
        """Verify that activities are deduplicated and changes are detected."""
        course = Course(course_id="bNVZvmOP6oqNqgQ9wRY7", name="Design Project (Part-I)", code="SE4912")
        self.db.upsert_course(course)

        deadline = datetime.now() + timedelta(days=4)
        activity = AcademicActivity(
            activity_id="act_001",
            course_id=course.course_id,
            course_name=course.name,
            activity_type=ActivityType.ASSIGNMENT,
            title="Proposal Report & Presentation",
            deadline=deadline,
            submission_status=SubmissionStatus.NOT_SUBMITTED
        )

        # 1st insertion: Must be new
        saved, is_new, changes = self.db.upsert_activity(activity)
        self.assertTrue(is_new)
        self.assertEqual(len(changes), 0)

        # 2nd insertion with same data: Must NOT be new and NO changes (no duplicate alerts)
        saved2, is_new2, changes2 = self.db.upsert_activity(activity)
        self.assertFalse(is_new2)
        self.assertEqual(len(changes2), 0)

        # 3rd insertion: Student submits assignment on portal!
        activity.submission_status = SubmissionStatus.SUBMITTED
        saved3, is_new3, changes3 = self.db.upsert_activity(activity)
        self.assertFalse(is_new3)
        self.assertIn("submission_status", changes3)
        self.assertEqual(changes3["submission_status"]["old"], "Not Submitted")
        self.assertEqual(changes3["submission_status"]["new"], "Submitted")

    def test_deadline_reminders(self):
        """Verify that deadline countdown triggers appropriately and halts when submitted."""
        course = Course(course_id="c_db", name="Database Systems")
        self.db.upsert_course(course)

        # Task due in 20 hours (within 24h threshold)
        act = AcademicActivity(
            activity_id="act_db_1",
            course_id="c_db",
            course_name="Database Systems",
            activity_type=ActivityType.ASSIGNMENT,
            title="ER Diagram Task",
            deadline=datetime.now() + timedelta(hours=20),
            submission_status=SubmissionStatus.NOT_SUBMITTED
        )
        self.db.upsert_activity(act)

        engine = DeadlineEngine(self.db, reminder_hours=[72, 48, 24, 12, 6, 3, 1])
        due = engine.evaluate_reminders()

        # Should trigger 24h reminder
        self.assertEqual(len(due), 1)
        activity, threshold = due[0]
        self.assertEqual(threshold, 24)

        # Mark 24h reminder sent
        self.db.record_reminder_sent(activity.activity_id, 24)

        # Re-evaluate: Should not trigger 24h again!
        due_again = engine.evaluate_reminders()
        self.assertEqual(len(due_again), 0)

        # Once submitted, no reminders should ever fire
        act.submission_status = SubmissionStatus.SUBMITTED
        self.db.upsert_activity(act)
        due_submitted = engine.evaluate_reminders()
        self.assertEqual(len(due_submitted), 0)

    def test_priority_classifier(self):
        """Verify smart priority assignment."""
        act_critical = AcademicActivity(
            activity_id="1", course_id="c", course_name="C",
            activity_type=ActivityType.ASSIGNMENT, title="Urgent Task",
            deadline=datetime.now() + timedelta(hours=8),
            submission_status=SubmissionStatus.NOT_SUBMITTED
        )
        p1 = PriorityClassifier.classify(act_critical)
        self.assertEqual(p1, PriorityLevel.CRITICAL)

        act_high = AcademicActivity(
            activity_id="2", course_id="c", course_name="C",
            activity_type=ActivityType.PROJECT, title="Course Term Project",
            deadline=datetime.now() + timedelta(days=5),
            submission_status=SubmissionStatus.NOT_SUBMITTED
        )
        p2 = PriorityClassifier.classify(act_high)
        self.assertEqual(p2, PriorityLevel.HIGH)

    def test_html_parser_with_user_sample(self):
        """Verify parsing of ODOCUST table structure matching user's real course page."""
        sample_html = """
        <html>
        <body>
            <a href="/student/course/info/bNVZvmOP6oqNqgQ9wRY7">Design Project (Part-I) (SE4912-263-BSE-233-1)</a>
            <table class="table">
                <thead>
                    <tr>
                        <th>Sr No.</th>
                        <th>Subject</th>
                        <th>Date</th>
                        <th>Description</th>
                        <th>Attachment</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>1</td>
                        <td>FYP Orientation</td>
                        <td>2026-09-21</td>
                        <td>Dear students, FYP Orientation will be held on Tuesday...</td>
                        <td></td>
                    </tr>
                    <tr>
                        <td>2</td>
                        <td>FYP Registrations - Final List</td>
                        <td>2026-09-24</td>
                        <td>The registration process is complete...</td>
                        <td><a href="/student/news/download/L8025K4gpYo5rboVw1vG">Download</a></td>
                    </tr>
                </tbody>
            </table>
        </body>
        </html>
        """
        courses = self.extractor.parse_dashboard_courses(sample_html)
        self.assertEqual(len(courses), 1)
        self.assertEqual(courses[0].course_id, "bNVZvmOP6oqNqgQ9wRY7")
        self.assertIn("Design Project", courses[0].name)

        announcements = self.extractor.parse_announcements(sample_html, courses[0])
        self.assertEqual(len(announcements), 2)
        self.assertEqual(announcements[0].title, "FYP Orientation")
        self.assertEqual(announcements[1].title, "FYP Registrations - Final List")
        self.assertTrue(announcements[1].attachment_url.endswith("/student/news/download/L8025K4gpYo5rboVw1vG"))

    def test_whatsapp_formatting(self):
        """Verify WhatsApp message formatting."""
        act = AcademicActivity(
            activity_id="test",
            course_id="c1",
            course_name="Database Systems",
            activity_type=ActivityType.ASSIGNMENT,
            title="ER Diagram Task",
            posted_date=datetime.now(),
            deadline=datetime.now() + timedelta(days=2, hours=14),
            submission_status=SubmissionStatus.NOT_SUBMITTED,
            portal_url="https://odoo.cust.edu.pk/student/course/submission/c1"
        )
        msg = NotificationFormatter.format_new_activity(act)
        self.assertIn("New Assignment Detected", msg)
        self.assertIn("Database Systems", msg)
        self.assertIn("ER Diagram Task", msg)
        self.assertIn("Not Submitted", msg)

    def test_fyp_highest_priority(self):
        """Verify that any activity belonging to FYP is escalated to CRITICAL priority."""
        fyp_act = AcademicActivity(
            activity_id="fyp_1",
            course_id="bNVZvmOP6oqNqgQ9wRY7",
            course_name="Design Project (Part-I)",
            activity_type=ActivityType.ANNOUNCEMENT,
            title="FYP Proposal Symposium Schedule",
            posted_date=datetime.now()
        )
        self.assertTrue(fyp_act.is_fyp)
        priority = PriorityClassifier.classify(fyp_act)
        self.assertEqual(priority, PriorityLevel.CRITICAL)

        msg = NotificationFormatter.format_new_activity(fyp_act)
        self.assertIn("FYP — HIGHEST PRIORITY", msg)

    def test_attendance_drop_alerting(self):
        """Verify attendance tracking and alert generation on decline or < 75%."""
        course = Course(
            course_id="c_iot",
            name="Internet of Things",
            code="SE4743",
            attendance_pct=85.0
        )
        self.db.upsert_course(course)

        # Attendance drops to 70%
        course.attendance_pct = 70.0
        c, old_att, new_att = self.db.upsert_course(course)
        self.assertEqual(old_att, 85.0)
        self.assertEqual(new_att, 70.0)

        alert_msg = NotificationFormatter.format_attendance_alert(course, old_att, new_att)
        self.assertIn("Internet of Things", alert_msg)
        self.assertIn("70.0%", alert_msg)
        self.assertIn("85.0%", alert_msg)
        self.assertIn("75%", alert_msg)

    def test_downloader_logic(self):
        """Verify DocumentDownloader filename sanitization and folder routing."""
        from engine.downloader import DocumentDownloader
        downloader = DocumentDownloader("test_downloads")
        
        # FYP routing
        fyp_act = AcademicActivity(
            activity_id="1", course_id="c", course_name="Design Project (Part-I)",
            activity_type=ActivityType.MATERIAL, title="Proposal Template.docx"
        )
        self.assertTrue(fyp_act.is_fyp)
        clean_name = downloader._sanitize_filename("Proposal: Version 1.0 (Final)?.docx")
        self.assertNotIn(":", clean_name)
        self.assertNotIn("?", clean_name)

        # Cleanup test dir
        if os.path.exists("test_downloads"):
            import shutil
            shutil.rmtree("test_downloads", ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
