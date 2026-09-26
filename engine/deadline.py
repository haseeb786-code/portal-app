from datetime import datetime
from typing import List, Tuple, Optional
from core.models import AcademicActivity, SubmissionStatus, PriorityLevel, NotificationRecord
from core.database import Database

class DeadlineEngine:
    def __init__(self, db: Database, reminder_hours: Optional[List[int]] = None):
        self.db = db
        # Sorted in descending order: e.g. [72, 48, 24, 12, 6, 3, 1]
        self.reminder_hours = sorted(reminder_hours or [72, 48, 24, 12, 6, 3, 1], reverse=True)

    def evaluate_reminders(self) -> List[Tuple[AcademicActivity, int]]:
        """
        Scans all activities and identifies any unsubmitted tasks that have reached a reminder threshold.
        Returns a list of tuples: (activity, hour_interval_reached)
        """
        due_reminders: List[Tuple[AcademicActivity, int]] = []
        all_activities = self.db.get_all_activities()

        now = datetime.now()

        for activity in all_activities:
            # 1. Skip if already submitted or graded
            if activity.submission_status in (SubmissionStatus.SUBMITTED, SubmissionStatus.GRADED):
                continue

            # 2. Skip if no deadline or already overdue past 24 hours
            if not activity.deadline:
                continue

            remaining_hours = activity.remaining_hours
            if remaining_hours is None or remaining_hours < 0:
                # Task is overdue - if overdue by less than 1 hour and not notified as overdue, could alert
                continue

            # 3. Check configured thresholds
            # An interval T is eligible if:
            # - remaining_hours <= T
            # - T has not been sent yet
            # - No strictly smaller interval S < T has been sent (time moves forward!)
            eligible_thresholds = []
            for threshold in self.reminder_hours:
                if remaining_hours <= threshold and threshold not in activity.reminders_sent:
                    # Check if any smaller threshold was already sent
                    if not any(s < threshold for s in activity.reminders_sent):
                        eligible_thresholds.append(threshold)

            if eligible_thresholds:
                # Trigger the most immediate (smallest) threshold reached
                target_threshold = min(eligible_thresholds)
                due_reminders.append((activity, target_threshold))

        return due_reminders
