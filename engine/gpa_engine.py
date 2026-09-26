import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("odocust.gpa_engine")

@dataclass
class GradeThreshold:
    letter: str
    min_pct: float
    gpa_point: float

# Official CUST (Capital University of Science & Technology) Grading Scale
CUST_GRADING_SCALE = [
    GradeThreshold("A", 85.0, 4.00),
    GradeThreshold("A-", 80.0, 3.66),
    GradeThreshold("B+", 75.0, 3.33),
    GradeThreshold("B", 71.0, 3.00),
    GradeThreshold("B-", 68.0, 2.66),
    GradeThreshold("C+", 64.0, 2.33),
    GradeThreshold("C", 60.0, 2.00),
    GradeThreshold("C-", 57.0, 1.66),
    GradeThreshold("D+", 54.0, 1.30),
    GradeThreshold("D", 50.0, 1.00),
    GradeThreshold("F", 0.0, 0.00),
]

class GPAEngine:
    """
    Intelligent Academic Analytics, CUST Grading & CGPA Projection Engine.
    Simulates What-If scenarios, target grades, and graduation CGPA optimization.
    """

    @staticmethod
    def percentage_to_grade(percentage: float) -> Tuple[str, float]:
        """Maps a total percentage to Letter Grade and Grade Point."""
        pct = round(percentage, 2)
        for threshold in CUST_GRADING_SCALE:
            if pct >= threshold.min_pct:
                return threshold.letter, threshold.gpa_point
        return "F", 0.00

    @staticmethod
    def grade_point_to_min_percentage(letter_grade: str) -> float:
        """Returns the minimum percentage required for a given letter grade."""
        letter = letter_grade.upper().strip()
        for threshold in CUST_GRADING_SCALE:
            if threshold.letter.upper() == letter:
                return threshold.min_pct
        return 0.0

    @staticmethod
    def calculate_marks_needed_in_final(
        sessional_obtained: float,
        sessional_total: float,
        final_exam_total: float,
        target_letter: str = "A"
    ) -> Dict[str, Any]:
        """
        Calculates how many marks out of `final_exam_total` a student needs
        to achieve the `target_letter` grade.
        
        Formula:
          Total Percentage = (sessional_obtained + marks_in_final) / (sessional_total + final_exam_total) * 100
        """
        target_pct = GPAEngine.grade_point_to_min_percentage(target_letter)
        total_possible = sessional_total + final_exam_total
        needed_total_marks = (target_pct / 100.0) * total_possible
        needed_in_final = needed_total_marks - sessional_obtained

        # Calculate max possible percentage if student gets full marks in final
        max_possible_pct = ((sessional_obtained + final_exam_total) / total_possible) * 100.0
        max_possible_grade, max_possible_gpa = GPAEngine.percentage_to_grade(max_possible_pct)

        is_achievable = needed_in_final <= final_exam_total
        already_secured = needed_in_final <= 0

        needed_final_pct = (needed_in_final / final_exam_total * 100.0) if final_exam_total > 0 else 0.0

        return {
            "target_grade": target_letter,
            "target_percentage": target_pct,
            "current_sessional": sessional_obtained,
            "sessional_total": sessional_total,
            "final_exam_total": final_exam_total,
            "marks_needed": round(max(0.0, needed_in_final), 2),
            "percentage_needed_in_final": round(max(0.0, needed_final_pct), 1),
            "is_achievable": is_achievable,
            "already_secured": already_secured,
            "max_reachable_grade": max_possible_grade,
            "max_reachable_percentage": round(max_possible_pct, 1),
            "status_message": (
                f"You already secured {target_letter}!" if already_secured else
                f"Need {round(needed_in_final, 1)}/{int(final_exam_total)} ({round(needed_final_pct, 1)}%) in Final Exam." if is_achievable else
                f"Cannot reach {target_letter}. Maximum possible grade is {max_possible_grade} ({round(max_possible_pct, 1)}%)."
            )
        }

    @staticmethod
    def simulate_all_targets_for_course(
        sessional_obtained: float,
        sessional_total: float,
        final_exam_total: float = 40.0
    ) -> List[Dict[str, Any]]:
        """Returns a breakdown of marks needed in Final Exam for all possible grades."""
        results = []
        for target in ["A", "A-", "B+", "B", "B-", "C+", "C"]:
            res = GPAEngine.calculate_marks_needed_in_final(
                sessional_obtained, sessional_total, final_exam_total, target
            )
            results.append(res)
        return results

    @staticmethod
    def project_cgpa(
        current_cgpa: float,
        completed_credits: int,
        semester_courses: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Projects semester GPA and overall graduating CGPA.
        
        semester_courses: List of dicts, e.g.:
        [
          {"course_name": "FYP - Design Project", "credits": 3, "expected_grade": "A"},
          {"course_name": "Software Quality", "credits": 3, "expected_grade": "B+"},
        ]
        """
        total_sem_credits = sum(c.get("credits", 3) for c in semester_courses)
        if total_sem_credits == 0:
            return {"semester_gpa": current_cgpa, "projected_cgpa": current_cgpa, "diff": 0.0}

        total_sem_quality_points = 0.0
        for c in semester_courses:
            grade = c.get("expected_grade", "B")
            credits = c.get("credits", 3)
            # Find grade point
            _, gpa_point = GPAEngine.percentage_to_grade(GPAEngine.grade_point_to_min_percentage(grade))
            total_sem_quality_points += (gpa_point * credits)

        semester_gpa = round(total_sem_quality_points / total_sem_credits, 2)

        # Cumulative calculation
        current_total_quality_points = current_cgpa * completed_credits
        new_total_quality_points = current_total_quality_points + total_sem_quality_points
        new_total_credits = completed_credits + total_sem_credits

        projected_cgpa = round(new_total_quality_points / new_total_credits, 2)
        diff = round(projected_cgpa - current_cgpa, 2)

        # Max possible calculation (All A's)
        max_sem_qp = 4.00 * total_sem_credits
        max_projected_cgpa = round((current_total_quality_points + max_sem_qp) / new_total_credits, 2)

        return {
            "current_cgpa": current_cgpa,
            "completed_credits": completed_credits,
            "semester_credits": total_sem_credits,
            "semester_gpa": semester_gpa,
            "projected_cgpa": projected_cgpa,
            "cgpa_change": diff,
            "max_possible_cgpa": max_projected_cgpa,
            "summary_advice": (
                f"With a {semester_gpa} GPA this semester, your CGPA changes from {current_cgpa} to {projected_cgpa} ({'+' if diff >= 0 else ''}{diff}). "
                f"Your highest mathematical ceiling this semester is {max_projected_cgpa} (All A's)."
            )
        }

    @staticmethod
    def get_strategic_advising(courses_status: List[Dict[str, Any]]) -> List[str]:
        """
        Generates tactical advice for the student (e.g. FYP priority, attendance risks).
        """
        advice = []
        for c in courses_status:
            name = c.get("name", "Course")
            att = c.get("attendance_pct", 100.0)
            is_fyp = c.get("is_fyp", False)

            if att < 75.0:
                advice.append(f"⚠️ CRITICAL: In {name}, attendance is {att:.1f}% (below 75% CUST threshold). You risk debarment!")
            elif att < 80.0:
                advice.append(f"⚡ WARNING: Attendance in {name} is {att:.1f}%. Do not miss any upcoming lectures.")

            if is_fyp:
                advice.append(f"🎓 FYP LEVERAGE: Final Year Project is heavily weighted. Maintaining an 'A' grade here protects your CGPA against smaller course fluctuations.")

        return advice
