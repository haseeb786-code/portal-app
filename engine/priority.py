from datetime import datetime
from typing import Optional, Dict, Any
from core.models import AcademicActivity, ActivityType, PriorityLevel, SubmissionStatus

class PriorityClassifier:
    @staticmethod
    def classify(activity: AcademicActivity, changes: Optional[Dict[str, Any]] = None) -> PriorityLevel:
        """
        Determines the priority level of an academic event based on:
        - Remaining time to deadline
        - Submission status
        - Activity type
        - Content urgency
        - Recent changes
        """
        # 0. FYP / Design Project items are ALWAYS treated as highest priority
        if activity.is_fyp:
            return PriorityLevel.CRITICAL

        # 1. Check for Critical changes (e.g. deadline moved earlier)
        if changes and "deadline" in changes:
            old_dl = changes["deadline"].get("old")
            new_dl = changes["deadline"].get("new")
            if old_dl and new_dl and new_dl < old_dl:
                return PriorityLevel.CRITICAL

        # 2. Check remaining hours if deadline exists
        hours = activity.remaining_hours
        if hours is not None:
            # Overdue or within 24 hours and not submitted
            if hours <= 24 and activity.submission_status not in (SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED):
                return PriorityLevel.CRITICAL
            
            # Within 24-72 hours (1 to 3 days)
            if 24 < hours <= 72 and activity.submission_status not in (SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED):
                return PriorityLevel.HIGH

        # 3. Urgency keywords in title or description
        urgent_keywords = ["urgent", "mandatory", "important", "immediate", "cancelled", "postponed", "defense", "symposium", "final list"]
        combined_text = f"{activity.title} {activity.description}".lower()
        if any(w in combined_text for w in urgent_keywords):
            if hours is not None and hours <= 48:
                return PriorityLevel.CRITICAL
            return PriorityLevel.HIGH

        # 4. Activity Type baseline
        if activity.activity_type == ActivityType.QUIZ:
            if hours is not None and hours <= 48:
                return PriorityLevel.CRITICAL
            return PriorityLevel.HIGH

        if activity.activity_type == ActivityType.PROJECT:
            return PriorityLevel.HIGH

        if activity.activity_type == ActivityType.ASSIGNMENT:
            if hours is not None and hours > 72:
                return PriorityLevel.NORMAL
            return PriorityLevel.HIGH

        if activity.activity_type == ActivityType.ANNOUNCEMENT:
            return PriorityLevel.NORMAL

        if activity.activity_type == ActivityType.MATERIAL:
            return PriorityLevel.LOW

        return PriorityLevel.NORMAL
