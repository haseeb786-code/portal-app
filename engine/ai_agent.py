import os
import re
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from core.models import AcademicActivity, Course
from engine.doc_parser import DocumentParser
from engine.gpa_engine import GPAEngine

logger = logging.getLogger("odocust.ai_agent")

class AcademicAIAgent:
    """
    Autonomous Academic Intelligence Agent.
    - Analyzes portal documents, assignments, and announcements.
    - Condenses any uploaded file into an actionable 2-3 line brief.
    - Calculates and simulates GPA improvement trajectories.
    - Investigates and searches missing portal information.
    - Powered by Gemini 3.8 Flash with graceful offline heuristic fallback.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.8-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("✅ Gemini AI Client initialized successfully for Academic Agent.")
            except Exception as e:
                logger.warning(f"Could not initialize Google GenAI client: {e}. Falling back to heuristic engine.")

    def analyze_document_and_summarize(self, activity: AcademicActivity, file_path: Optional[str] = None) -> str:
        """
        Parses the document attachment and generates a 2-3 sentence executive summary.
        Saves the summary on the activity object.
        """
        target_file = file_path or activity.local_file_path
        if not target_file or not os.path.exists(target_file):
            # Fallback to activity description if no document file
            if activity.description and len(activity.description.strip()) > 30:
                text_content = activity.description
            else:
                return f"No document attached. {activity.title} in {activity.course_name}."
        else:
            text_content = DocumentParser.extract_text(target_file, max_chars=12000)

        if not text_content or len(text_content.strip()) < 20:
            return f"Document uploaded for {activity.title}. Contents could not be textually extracted (scanned or binary)."

        # 1. If Gemini Client is configured, run LLM summarization
        if self.client:
            try:
                prompt = (
                    f"You are an academic advisor for a Computer Science student at Capital University of Science & Technology (CUST).\n"
                    f"Analyze this university document:\n"
                    f"Course: {activity.course_name}\n"
                    f"Item: {activity.title} ({activity.activity_type.value})\n"
                    f"Document Content Preview:\n{text_content[:8000]}\n\n"
                    f"Provide a crisp, actionable 2-3 sentence executive brief:\n"
                    f"1. Core Task/Announcement: What exactly is required?\n"
                    f"2. Key Deliverable & Format: Required output (code, report, Excel, etc.).\n"
                    f"3. Practical Tip: Key deadline, high-weight question, or advice.\n"
                    f"Total length: Under 60 words. Strict, no conversational filler."
                )

                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                summary = response.text.strip()
                logger.info(f"✨ Gemini AI successfully generated 3-line summary for: {activity.title}")
                return summary
            except Exception as e:
                logger.warning(f"Gemini API call failed ({e}). Using local heuristic extractor.")

        # 2. High-Quality Local Heuristic Extraction (Instant & Offline)
        return self._heuristic_document_summary(activity, text_content)

    def _heuristic_document_summary(self, activity: AcademicActivity, text: str) -> str:
        """
        Intelligent rule-based extractor that finds tasks, requirements, and due dates
        directly from document text when offline.
        """
        lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 15]
        
        # Look for action verbs / keywords
        task_sentences = []
        deliverable_sentences = []
        warning_sentences = []

        keywords_task = ["develop", "implement", "create", "write", "design", "solve", "schedule", "symposium", "registration", "status"]
        keywords_deliv = ["submit", "submission", "pdf", "word", "github", "zip", "format", "report", "presentation", "sheet"]
        keywords_warn = ["deadline", "due", "marks", "late", "plagiarism", "penalty", "attendance", "must", "strictly"]

        for line in lines:
            lower = line.lower()
            if any(k in lower for k in keywords_task) and len(task_sentences) < 2:
                task_sentences.append(line[:120])
            elif any(k in lower for k in keywords_deliv) and len(deliverable_sentences) < 2:
                deliverable_sentences.append(line[:120])
            elif any(k in lower for k in keywords_warn) and len(warning_sentences) < 1:
                warning_sentences.append(line[:120])

        summary_parts = []
        if task_sentences:
            summary_parts.append(f"📌 Task: {task_sentences[0]}")
        else:
            summary_parts.append(f"📌 Task: Overview of {activity.title} for {activity.course_name}.")

        if deliverable_sentences:
            summary_parts.append(f"📦 Deliverable: {deliverable_sentences[0]}")

        if warning_sentences:
            summary_parts.append(f"⚠️ Note: {warning_sentences[0]}")
        elif activity.deadline:
            summary_parts.append(f"⏰ Due: {activity.deadline.strftime('%b %d, %I:%M %p')}")

        return "\n".join(summary_parts[:3])

    def answer_query(self, user_query: str, db_context: Dict[str, Any]) -> str:
        """
        Answers conversational student queries using live portal & database context.
        Handles GPA questions, deadline lookups, and document questions.
        """
        q = user_query.lower().strip()

        # 1. GPA calculation queries
        if any(w in q for w in ["gpa", "cgpa", "grade", "marks", "improve", "percentage", "final exam"]):
            return self._handle_gpa_query(q, db_context)

        # 2. Deadlines and Pending items
        if any(w in q for w in ["deadline", "due", "pending", "assignment", "quiz", "what do i have"]):
            return self._handle_deadline_query(db_context)

        # 3. FYP questions
        if any(w in q for w in ["fyp", "design project", "symposium", "proposal"]):
            return self._handle_fyp_query(db_context)

        # 4. If Gemini is available, pass the full context for natural answer
        if self.client:
            try:
                system_context = (
                    f"Courses enrolled: {[c.name for c in db_context.get('courses', [])]}\n"
                    f"Pending activities: {len(db_context.get('pending_activities', []))}\n"
                    f"Recent downloads: {len(db_context.get('downloaded_files', []))}\n"
                )
                prompt = (
                    f"You are the student's personal Academic Copilot for Capital University of Science & Technology.\n"
                    f"Context:\n{system_context}\n\n"
                    f"Student Question: {user_query}\n"
                    f"Provide a helpful, precise answer in 2-4 sentences."
                )
                res = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                return res.text.strip()
            except Exception as e:
                logger.warning(f"Gemini query failed: {e}")

        # Default fallback
        courses = db_context.get("courses", [])
        pending = db_context.get("pending_activities", [])
        return (
            f"You currently have {len(courses)} active courses monitored on ODOCUST, "
            f"with {len(pending)} pending tasks. Ask me about specific course deadlines, "
            f"target GPA calculations, or document summaries!"
        )

    def _handle_gpa_query(self, query: str, context: Dict[str, Any]) -> str:
        current_cgpa = float(context.get("current_cgpa", 3.20))
        completed_credits = int(context.get("completed_credits", 100))
        courses = context.get("courses", [])

        # Default 7th semester load: ~5 courses, 3 credits each
        semester_courses = [{"course_name": c.name, "credits": 3, "expected_grade": "A"} for c in courses]
        if not semester_courses:
            semester_courses = [
                {"course_name": "FYP - Design Project", "credits": 3, "expected_grade": "A"},
                {"course_name": "Course 2", "credits": 3, "expected_grade": "A"},
                {"course_name": "Course 3", "credits": 3, "expected_grade": "A-"},
                {"course_name": "Course 4", "credits": 3, "expected_grade": "B+"},
            ]

        projection = GPAEngine.project_cgpa(current_cgpa, completed_credits, semester_courses)

        return (
            f"📊 **GPA & Improvement Projection (CUST Scale):**\n"
            f"• Current CGPA: {current_cgpa} (after {completed_credits} credit hours)\n"
            f"• Potential Semester GPA: {projection['semester_gpa']} (if you achieve target grades)\n"
            f"• **New Graduating CGPA:** {projection['projected_cgpa']} ({'+' if projection['cgpa_change'] >= 0 else ''}{projection['cgpa_change']})\n"
            f"• **Mathematical Ceiling:** Highest possible CGPA is **{projection['max_possible_cgpa']}** if you secure straight A's in all courses.\n\n"
            f"💡 *Pro-Tip:* Final Year Project (FYP) has maximum leverage. Keeping an 'A' in FYP prevents sessional drops in other subjects from dragging your overall degree CGPA down."
        )

    def _handle_deadline_query(self, context: Dict[str, Any]) -> str:
        pending = context.get("pending_activities", [])
        if not pending:
            return "🎉 Great news! You have no pending submissions or urgent deadlines right now."

        lines = ["📅 **Upcoming Deadlines & Pending Tasks:**"]
        for p in pending[:5]:
            rem = p.remaining_str()
            lines.append(f"• **[{p.course_name}]** {p.title} ⏳ *{rem}*")
        return "\n".join(lines)

    def _handle_fyp_query(self, context: Dict[str, Any]) -> str:
        fyp_items = [a for a in context.get("all_activities", []) if a.is_fyp]
        downloaded = [f for f in context.get("downloaded_files", []) if "fyp" in f.lower()]

        res = ["🎓 **FYP (Final Year Project) Status:**"]
        if fyp_items:
            res.append(f"• Active FYP Announcements/Tasks: {len(fyp_items)}")
            for item in fyp_items[:3]:
                res.append(f"  - {item.title} ({item.submission_status.value})")
        if downloaded:
            res.append(f"• Downloaded Guidelines/Schedules: {len(downloaded)} files in `downloads/FYP - Design Project/`")
        return "\n".join(res)
