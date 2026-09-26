"""
Sessional Margin Guard — 15-Mark Buffer Tracker
================================================
Tracks marks obtained per component (Quiz, Assignment, Midterm, Lab)
per course and calculates, in real time, how many marks remain before
a student's total sessional percentage drops below 85% (grade A boundary).

Alert levels
------------
  🔴 CRITICAL  — fewer than 6 marks of buffer remaining
  🟡 WARNING   — 6-14 marks of buffer remaining
  🟢 SAFE      — 15+ marks of buffer remaining
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("odocust.margin_guard")

# CUST sessional grade boundary (usually 60 marks out of 100 total sessional)
# The sessional contributes up to 60% of the total grade.
# To get an A (≥85% overall), a student generally needs ≥51/60 sessionally.
# We guard so that any drop below that "85-line" is flagged early.

CUST_A_BOUNDARY = 85.0   # overall percentage needed for grade A
CRITICAL_BUFFER = 6      # alert if ≤ 6 marks left before dropping below A line
WARNING_BUFFER = 15      # warn if ≤ 15 marks left


@dataclass
class CourseMarksEntry:
    """Represents the marks obtained for one component in a course."""
    course_id: str
    course_name: str
    component: str       # e.g. "Quiz 1", "Assignment 2", "Midterm"
    obtained: float
    total: float
    component_type: str  # "quiz" | "assignment" | "midterm" | "lab" | "other"
    entered_at: str      # ISO timestamp


@dataclass
class MarginReport:
    """Report for one course."""
    course_id: str
    course_name: str
    # Sessional component marks
    components: List[CourseMarksEntry] = field(default_factory=list)

    # Totals across entered components
    obtained_total: float = 0.0
    possible_total: float = 0.0          # total marks of entered components

    # Percentage within entered components
    current_pct: float = 0.0

    # Marks remaining until the A-boundary is violated
    marks_buffer: float = 0.0

    # Alert level: "safe" | "warning" | "critical"
    alert_level: str = "safe"

    # Human-readable message
    message: str = ""

    # Hypothetical full sessional total (CUST typically uses 60-mark sessional)
    sessional_total: float = 60.0


class MarginGuard:
    """
    Core logic for the Sessional Margin Guard.
    Stateless — all data comes from the database; this class only computes.
    """

    @staticmethod
    def compute_margin(entries: List[CourseMarksEntry],
                       sessional_total: float = 60.0,
                       overall_total: float = 100.0) -> Dict:
        """
        Given a list of mark entries for a course, compute the margin report.

        Parameters
        ----------
        entries         : All mark entries for this course
        sessional_total : Maximum marks for the sessional part (default 60)
        overall_total   : Maximum marks for the course overall (default 100)

        Returns a dict suitable for JSON serialisation.
        """
        if not entries:
            return {
                "obtained_total": 0,
                "possible_total": 0,
                "remaining_sessional": sessional_total,
                "current_pct": 0.0,
                "marks_needed_for_A": round(CUST_A_BOUNDARY / 100 * sessional_total, 1),
                "marks_buffer": round(CUST_A_BOUNDARY / 100 * sessional_total, 1),
                "alert_level": "safe",
                "message": "No marks entered yet."
            }

        obtained = sum(e.obtained for e in entries)
        possible = sum(e.total for e in entries)

        # How much of the sessional is still un-entered?
        remaining_sessional = max(0.0, sessional_total - possible)

        # Marks needed in the FULL sessional to reach A boundary
        marks_needed_for_A = (CUST_A_BOUNDARY / 100.0) * sessional_total  # e.g. 51 out of 60

        # Marks still needed from remaining components to reach that target
        marks_buffer = max(0.0, marks_needed_for_A - obtained)

        # Current percentage within entered components
        current_pct = (obtained / possible * 100.0) if possible > 0 else 0.0

        # Determine alert level
        if marks_buffer <= CRITICAL_BUFFER and remaining_sessional < marks_buffer:
            alert_level = "critical"
            message = (
                f"CRITICAL: You need {marks_buffer:.1f} more marks in remaining "
                f"{remaining_sessional:.0f} sessional marks to keep an A. "
                f"Nearly impossible — act now."
            )
        elif marks_buffer <= CRITICAL_BUFFER:
            alert_level = "critical"
            message = (
                f"CRITICAL: Only {marks_buffer:.1f} marks of buffer left before "
                f"dropping below A. Nail every remaining quiz and assignment."
            )
        elif marks_buffer <= WARNING_BUFFER:
            alert_level = "warning"
            message = (
                f"WARNING: {marks_buffer:.1f} marks buffer remaining. "
                f"Avoid losing marks on upcoming components to secure your A."
            )
        else:
            alert_level = "safe"
            message = (
                f"SAFE: {marks_buffer:.1f} marks buffer. "
                f"Keep up the current performance to maintain grade A."
            )

        return {
            "obtained_total": round(obtained, 2),
            "possible_total": round(possible, 2),
            "remaining_sessional": round(remaining_sessional, 2),
            "current_pct": round(current_pct, 2),
            "marks_needed_for_A": round(marks_needed_for_A, 1),
            "marks_buffer": round(marks_buffer, 1),
            "alert_level": alert_level,
            "message": message
        }

    @staticmethod
    def build_telegram_alert(course_name: str, margin: Dict) -> Optional[str]:
        """
        Returns a Telegram-formatted alert string if the course is in critical/warning state,
        or None if safe.
        """
        level = margin["alert_level"]
        if level == "safe":
            return None

        emoji = "🔴" if level == "critical" else "🟡"
        return (
            f"{emoji} *MARGIN ALERT — {course_name}*\n"
            f"Obtained: {margin['obtained_total']}/{margin['possible_total']} "
            f"({margin['current_pct']:.1f}%)\n"
            f"Buffer until A drops: *{margin['marks_buffer']} marks*\n"
            f"_{margin['message']}_"
        )
