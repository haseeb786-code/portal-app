from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

class ActivityType(str, Enum):
    ASSIGNMENT = "Assignment"
    PROJECT = "Project"
    QUIZ = "Quiz"
    ANNOUNCEMENT = "Announcement"
    MATERIAL = "Material"
    EXAM = "Exam"
    OTHER = "Other"

class SubmissionStatus(str, Enum):
    NOT_SUBMITTED = "Not Submitted"
    SUBMITTED = "Submitted"
    LATE_SUBMITTED = "Late Submitted"
    GRADED = "Graded"
    UNKNOWN = "Unknown"

class PriorityLevel(str, Enum):
    CRITICAL = "CRITICAL"  # 🔴 < 24h deadline, submission failure, imminent quiz
    HIGH = "HIGH"          # 🟠 2-3 days deadline, new project/assignment
    NORMAL = "NORMAL"      # 🟡 Plenty of time, general course announcement
    LOW = "LOW"            # 🟢 Informational updates

@dataclass
class Course:
    course_id: str
    name: str
    code: str = ""
    instructor: str = ""
    url: str = ""
    attendance_pct: float = 100.0
    last_synced: Optional[datetime] = None

    @property
    def is_fyp(self) -> bool:
        return any(k in f"{self.name} {self.code}".lower() for k in ["fyp", "design project", "final year", "se4912"])

@dataclass
class AcademicActivity:
    activity_id: str
    course_id: str
    course_name: str
    activity_type: ActivityType
    title: str
    description: str = ""
    posted_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    submission_status: SubmissionStatus = SubmissionStatus.UNKNOWN
    marks: str = ""
    attachment_url: str = ""
    attachment_name: str = ""
    local_file_path: str = ""
    portal_url: str = ""
    priority: PriorityLevel = PriorityLevel.NORMAL
    first_seen_at: datetime = field(default_factory=datetime.now)
    last_checked_at: datetime = field(default_factory=datetime.now)
    first_notified_at: Optional[datetime] = None
    reminders_sent: List[int] = field(default_factory=list)  # e.g. [72, 48, 24, 12, 6, 3, 1]

    @property
    def is_fyp(self) -> bool:
        return any(k in f"{self.course_name} {self.title}".lower() for k in ["fyp", "design project", "final year", "se4912", "symposium", "proposal defense"])

    @property
    def remaining_hours(self) -> Optional[float]:
        if not self.deadline:
            return None
        diff = (self.deadline - datetime.now()).total_seconds() / 3600.0
        return diff

    @property
    def is_overdue(self) -> bool:
        if not self.deadline:
            return False
        return datetime.now() > self.deadline

    def remaining_str(self) -> str:
        if not self.deadline:
            return "No deadline specified"
        diff = self.deadline - datetime.now()
        total_seconds = int(diff.total_seconds())
        if total_seconds < 0:
            return "⚠️ Overdue"
        
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days > 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hr{'s' if hours > 1 else ''}")
        if days == 0 and minutes > 0:
            parts.append(f"{minutes} min{'s' if minutes > 1 else ''}")
            
        return " ".join(parts) if parts else "Due right now!"

@dataclass
class NotificationRecord:
    activity_id: Optional[str]
    notification_type: str  # 'NEW', 'REMINDER', 'STATUS_CHANGE', 'DAILY_SUMMARY', 'ALERT'
    priority: PriorityLevel
    message_text: str
    status: str = "PENDING"  # 'SENT', 'FAILED'
    sent_at: Optional[datetime] = None
    error_message: str = ""
