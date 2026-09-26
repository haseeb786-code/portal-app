from datetime import datetime
from typing import List, Dict, Any, Optional
from core.models import AcademicActivity, Course, ActivityType, SubmissionStatus, PriorityLevel

class NotificationFormatter:
    @staticmethod
    def format_new_activity(activity: AcademicActivity) -> str:
        """
        Formats a notification for newly discovered assignments, projects, quizzes, or announcements.
        """
        priority_icon = {
            PriorityLevel.CRITICAL: "🔴 [CRITICAL]",
            PriorityLevel.HIGH: "🟠 [HIGH]",
            PriorityLevel.NORMAL: "🟡",
            PriorityLevel.LOW: "🟢"
        }.get(activity.priority, "")

        if activity.is_fyp:
            header = "🚨🎓 *[FYP — HIGHEST PRIORITY]*"
        elif activity.activity_type == ActivityType.PROJECT:
            header = "🚨 *New Project Posted*"
        elif activity.activity_type == ActivityType.QUIZ or activity.activity_type == ActivityType.EXAM:
            header = "📝 *New Quiz / Assessment Notification*"
        elif activity.activity_type == ActivityType.ASSIGNMENT:
            header = "📚 *New Assignment Detected*"
        else:
            header = "🔔 *Important ODO Announcement*"

        deadline_str = activity.deadline.strftime("%d %B, %I:%M %p") if activity.deadline else "No deadline"
        posted_str = activity.posted_date.strftime("%d %B") if activity.posted_date else "Today"

        lines = [
            f"{header} {priority_icon}".strip(),
            "",
            f"📌 *Course:* {activity.course_name}",
            f"🎯 *Title:* {activity.title}"
        ]

        if activity.posted_date:
            lines.append(f"📅 *Posted:* {posted_str}")

        if activity.deadline:
            lines.append(f"⏳ *Deadline:* {deadline_str}")
            lines.append(f"⏱️ *Remaining:* {activity.remaining_str()}")

        if activity.activity_type in (ActivityType.ASSIGNMENT, ActivityType.PROJECT):
            status_emoji = "✅" if activity.submission_status == SubmissionStatus.SUBMITTED else "⚠️"
            lines.append(f"📋 *Status:* {status_emoji} {activity.submission_status.value}")

        if activity.marks:
            lines.append(f"📊 *Marks:* {activity.marks}")

        if activity.description:
            clean_desc = (activity.description[:250] + "...") if len(activity.description) > 250 else activity.description
            lines.append(f"\n💬 *Details:*\n{clean_desc}")

        if activity.local_file_path:
            lines.append(f"📥 *Downloaded Locally:* `{activity.local_file_path}`")
        elif activity.attachment_url:
            lines.append(f"📎 *Attachment:* {activity.attachment_url}")

        if activity.portal_url:
            lines.append(f"\n🔗 *Open Portal:* {activity.portal_url}")

        return "\n".join(lines)

    @staticmethod
    def format_deadline_reminder(activity: AcademicActivity, hours_threshold: int) -> str:
        """
        Formats an intelligent countdown reminder.
        """
        deadline_str = activity.deadline.strftime("%d %b, %I:%M %p") if activity.deadline else "Upcoming"
        urgency_indicator = "🚨 URGENT" if hours_threshold <= 24 else "⏰"

        return f"""{urgency_indicator} *Deadline Reminder ({hours_threshold}h Left)*

📌 *Course:* {activity.course_name}
🎯 *Task:* {activity.title}

⏳ *Deadline:* {deadline_str}
⏱️ *Remaining:* {activity.remaining_str()}

📋 *Status:* ⚠️ {activity.submission_status.value}

⚠️ *Submit before the deadline to avoid late penalties!*
🔗 *Portal Link:* {activity.portal_url}"""

    @staticmethod
    def format_status_change(activity: AcademicActivity, old_status: str, new_status: str) -> str:
        """
        Formats confirmation when submission status changes.
        """
        if new_status in (SubmissionStatus.SUBMITTED.value, SubmissionStatus.GRADED.value):
            return f"""✅ *Submission Confirmed*

📌 *Course:* {activity.course_name}
🎯 *Task:* {activity.title}
📋 *Status:* {new_status}
🕒 *Timestamp:* {datetime.now().strftime('%d %B, %I:%M %p')}

Great job completing this task!
🔗 {activity.portal_url}"""
        else:
            return f"""⚠️ *Submission Status Alert*

📌 *Course:* {activity.course_name}
🎯 *Task:* {activity.title}
📋 *New Status:* {new_status} (Previously: {old_status})

Please verify your portal submission immediately:
🔗 {activity.portal_url}"""

    @staticmethod
    def format_daily_summary(
        new_items: List[AcademicActivity],
        upcoming_items: List[AcademicActivity],
        unsubmitted_items: List[AcademicActivity],
        submitted_items: List[AcademicActivity],
        dashboard_url: str
    ) -> str:
        """
        Formats the daily WhatsApp morning briefing.
        """
        today_str = datetime.now().strftime("%d %B %Y")
        lines = [
            f"📊 *DAILY ACADEMIC SUMMARY*",
            f"📅 Today — {today_str}",
            "━━━━━━━━━━━━━━━━━━━━"
        ]

        if new_items:
            lines.append("\n🆕 *New Activities:*")
            for item in new_items[:5]:
                lines.append(f"• [{item.activity_type.value}] {item.course_name}: {item.title}")

        if upcoming_items:
            lines.append("\n⏰ *Upcoming Deadlines:*")
            for item in upcoming_items[:6]:
                lines.append(f"• {item.course_name} — {item.title} ({item.remaining_str()} left)")
        else:
            lines.append("\n⏰ *Upcoming Deadlines:* No immediate deadlines today! 🎉")

        if unsubmitted_items:
            lines.append("\n⚠️ *Pending Submissions:*")
            for item in unsubmitted_items[:6]:
                lines.append(f"• {item.course_name}: {item.title}")

        if submitted_items:
            lines.append("\n✅ *Completed / Submitted:*")
            for item in submitted_items[:5]:
                lines.append(f"• {item.course_name}: {item.title}")

        lines.append(f"\n🔗 *Open ODOCUST Dashboard:* {dashboard_url}")
        return "\n".join(lines)

    @staticmethod
    def format_system_alert(error_message: str, portal_url: str) -> str:
        """
        Formats portal connection / session failure warnings.
        """
        return f"""⚠️ *ODOCUST Monitoring Alert*

The system encountered an issue checking your student portal:

❌ *Reason:* {error_message}

Please check your credentials or re-authenticate on the dashboard to resume continuous monitoring.
🔗 *Portal:* {portal_url}"""

    @staticmethod
    def format_attendance_alert(course: Course, old_pct: Optional[float], new_pct: float) -> str:
        """
        Formats an alert when subject attendance drops or falls below critical 75% threshold.
        """
        is_critical = new_pct < 75.0
        icon = "🚨 [CRITICAL ATTENDANCE]" if is_critical else "⚠️ [ATTENDANCE UPDATE]"
        
        lines = [
            f"{icon} *{course.name}*",
            "",
            f"📊 *Current Attendance:* {new_pct:.1f}%",
        ]
        if old_pct is not None:
            lines.append(f"📉 *Previous Attendance:* {old_pct:.1f}%")
            
        if is_critical:
            lines.append("\n❗ *CRITICAL WARNING:* Attendance has dropped below the 75% minimum eligibility requirement for final examinations!")
        else:
            lines.append("\n⚠️ *Notice:* Attendance decline detected for this course. Ensure you attend upcoming classes.")
            
        if course.url:
            lines.append(f"\n🔗 *Portal Link:* {course.url}")
            
        return "\n".join(lines)
