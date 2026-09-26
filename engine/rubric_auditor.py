"""
Pre-Submission AI Rubric Auditor
=================================
Watches a `submissions/` folder for student-drafted files.
When a draft appears:
  1. Finds the matching assignment PDF/description in `downloads/`.
  2. Sends both to Gemini for a rubric-comparison audit.
  3. Returns a checklist of missing rubric items, formatting issues,
     and question coverage gaps.
  4. Stores the audit result in the database and sends a Telegram alert.

Can also be triggered on-demand via the dashboard API.
"""

import os
import logging
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

from engine.doc_parser import DocumentParser

logger = logging.getLogger("odocust.rubric_auditor")

SUBMISSIONS_DIR = Path("submissions")
DOWNLOADS_DIR = Path("downloads")


class RubricAuditor:
    """
    Pre-Submission AI Rubric Auditor.
    Compares a student's draft against the assignment rubric/description
    and produces an actionable gap-analysis checklist.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-3.8-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = model_name
        self.client = None

        if self.api_key:
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
                logger.info("[OK] Gemini Client initialized for Rubric Auditor.")
            except Exception as e:
                logger.warning(f"GenAI client error: {e}. Will use heuristic auditor.")

        # Ensure submissions dir exists
        SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def audit_draft(
        self,
        draft_path: str,
        assignment_description: str = "",
        assignment_file_path: str = "",
        course_name: str = "",
        assignment_title: str = ""
    ) -> Dict[str, Any]:
        """
        Run a full rubric audit on the provided draft file.

        Parameters
        ----------
        draft_path            : Absolute path to the student's draft file.
        assignment_description: Text description of the assignment (from DB).
        assignment_file_path  : Path to the downloaded assignment PDF/DOCX.
        course_name           : Course name for context.
        assignment_title      : Assignment title for context.

        Returns
        -------
        dict with keys:
            draft_file, assignment_file, audit_result (str),
            missing_items (list[str]), formatting_issues (list[str]),
            coverage_score (int 0-100), audited_at (ISO str)
        """
        draft_path = Path(draft_path)
        if not draft_path.exists():
            return self._error_result(f"Draft file not found: {draft_path}")

        # Extract draft text
        draft_text = DocumentParser.extract_text(str(draft_path), max_chars=10000)
        if not draft_text or len(draft_text.strip()) < 30:
            return self._error_result("Could not extract text from draft (scanned/binary).")

        # Extract rubric / assignment text
        rubric_text = assignment_description or ""
        if assignment_file_path and Path(assignment_file_path).exists():
            rubric_text = DocumentParser.extract_text(assignment_file_path, max_chars=6000)
        
        if not rubric_text:
            rubric_text = self._find_rubric_in_downloads(assignment_title, course_name)

        # Run audit
        if self.client and rubric_text:
            return self._gemini_audit(draft_text, rubric_text, draft_path.name,
                                      course_name, assignment_title)
        else:
            return self._heuristic_audit(draft_text, rubric_text, draft_path.name,
                                         course_name, assignment_title)

    def scan_submissions_folder(self) -> List[Dict[str, Any]]:
        """
        Scans the `submissions/` folder for any new/unaudited draft files.
        Returns a list of audit results for all found files.
        """
        results = []
        for f in SUBMISSIONS_DIR.glob("**/*"):
            if f.is_file() and f.suffix.lower() in [".pdf", ".docx", ".txt", ".zip", ".py"]:
                logger.info(f"Found draft for audit: {f.name}")
                result = self.audit_draft(str(f))
                results.append(result)
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_rubric_in_downloads(self, title: str, course_name: str) -> str:
        """
        Tries to find a matching assignment file in the downloads/ directory
        based on fuzzy name matching.
        """
        if not DOWNLOADS_DIR.exists():
            return ""

        title_words = set(title.lower().split()) if title else set()
        course_words = set(course_name.lower().split()) if course_name else set()

        best_match: Optional[Path] = None
        best_score = 0

        for f in DOWNLOADS_DIR.glob("**/*"):
            if not f.is_file():
                continue
            fname = f.stem.lower()
            score = sum(1 for w in title_words if w in fname)
            score += sum(1 for w in course_words if w in fname)
            if score > best_score:
                best_score = score
                best_match = f

        if best_match and best_score > 0:
            logger.info(f"Matched rubric file: {best_match.name} (score={best_score})")
            return DocumentParser.extract_text(str(best_match), max_chars=5000)
        return ""

    def _gemini_audit(self, draft: str, rubric: str, filename: str,
                      course_name: str, title: str) -> Dict[str, Any]:
        """Sends draft + rubric to Gemini and parses the structured audit."""
        prompt = (
            f"You are a strict academic reviewer at Capital University of Science & Technology (CUST).\n"
            f"Course: {course_name or 'N/A'}\n"
            f"Assignment: {title or filename}\n\n"
            f"=== ASSIGNMENT RUBRIC / DESCRIPTION ===\n{rubric[:5000]}\n\n"
            f"=== STUDENT DRAFT ===\n{draft[:8000]}\n\n"
            f"Perform a rubric audit. Respond in this EXACT format:\n\n"
            f"COVERAGE_SCORE: <0-100 integer>\n\n"
            f"MISSING_ITEMS:\n"
            f"- <missing item 1>\n"
            f"- <missing item 2>\n"
            f"(list every rubric requirement not addressed in the draft)\n\n"
            f"FORMATTING_ISSUES:\n"
            f"- <issue 1>\n"
            f"(list any formatting/structure problems: missing sections, wrong file format, etc.)\n\n"
            f"QUICK_SUMMARY:\n"
            f"<2-sentence overall verdict and top priority fix>\n\n"
            f"Be strict, concrete, and student-friendly. No fluff."
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            raw = response.text.strip()
            return self._parse_gemini_response(raw, filename)
        except Exception as e:
            logger.warning(f"Gemini rubric audit failed: {e}. Falling back to heuristic.")
            return self._heuristic_audit(draft, rubric, filename, course_name, title)

    def _parse_gemini_response(self, raw: str, filename: str) -> Dict[str, Any]:
        """Parses the structured Gemini rubric audit response."""
        import re

        # Coverage score
        score_m = re.search(r'COVERAGE_SCORE:\s*(\d+)', raw)
        coverage_score = int(score_m.group(1)) if score_m else 50

        # Missing items
        missing_block = re.search(r'MISSING_ITEMS:\s*\n(.*?)(?:FORMATTING_ISSUES:|$)', raw, re.S)
        missing_items = []
        if missing_block:
            for line in missing_block.group(1).strip().split("\n"):
                line = line.strip().lstrip("-").strip()
                if line and len(line) > 3:
                    missing_items.append(line)

        # Formatting issues
        fmt_block = re.search(r'FORMATTING_ISSUES:\s*\n(.*?)(?:QUICK_SUMMARY:|$)', raw, re.S)
        formatting_issues = []
        if fmt_block:
            for line in fmt_block.group(1).strip().split("\n"):
                line = line.strip().lstrip("-").strip()
                if line and len(line) > 3:
                    formatting_issues.append(line)

        # Quick summary
        summary_m = re.search(r'QUICK_SUMMARY:\s*\n(.*?)$', raw, re.S)
        quick_summary = summary_m.group(1).strip() if summary_m else raw[:300]

        return {
            "draft_file": filename,
            "assignment_file": "",
            "audit_result": quick_summary,
            "missing_items": missing_items,
            "formatting_issues": formatting_issues,
            "coverage_score": coverage_score,
            "audited_at": datetime.now().isoformat(),
            "method": "gemini"
        }

    def _heuristic_audit(self, draft: str, rubric: str, filename: str,
                         course_name: str, title: str) -> Dict[str, Any]:
        """
        Rule-based offline rubric checker.
        Checks for common academic submission requirements.
        """
        missing_items = []
        formatting_issues = []

        draft_lower = draft.lower()

        # Common academic doc requirements
        EXPECTED_SECTIONS = [
            ("introduction", ["introduction", "intro", "overview", "background"]),
            ("methodology", ["methodology", "approach", "method", "procedure", "algorithm"]),
            ("results", ["result", "output", "finding", "analysis", "experiment"]),
            ("conclusion", ["conclusion", "summary", "final remarks"]),
            ("references", ["references", "bibliography", "citations"]),
        ]

        for section_name, keywords in EXPECTED_SECTIONS:
            if not any(k in draft_lower for k in keywords):
                missing_items.append(f"Missing section: {section_name.capitalize()}")

        # Check against rubric keywords
        if rubric:
            rubric_lines = [l.strip() for l in rubric.split("\n") if len(l.strip()) > 10]
            for line in rubric_lines[:20]:
                words = [w.lower() for w in line.split() if len(w) > 4]
                if words and not any(w in draft_lower for w in words[:3]):
                    missing_items.append(f"Rubric point not addressed: {line[:80]}")

        # Formatting checks
        if len(draft.split()) < 200:
            formatting_issues.append("Document is very short (< 200 words). Check submission requirements.")
        if draft.count("\n") < 10:
            formatting_issues.append("Content seems unstructured — no section breaks detected.")
        if not any(c.isdigit() for c in draft):
            formatting_issues.append("No numeric data found — expected tables, figures, or data values.")

        coverage = max(0, 100 - len(missing_items) * 12 - len(formatting_issues) * 5)

        summary = (
            f"Heuristic audit complete for {filename}. "
            f"Found {len(missing_items)} missing rubric items and {len(formatting_issues)} formatting issues. "
            f"Coverage score: {coverage}/100."
        )

        return {
            "draft_file": filename,
            "assignment_file": "",
            "audit_result": summary,
            "missing_items": missing_items[:10],
            "formatting_issues": formatting_issues[:5],
            "coverage_score": coverage,
            "audited_at": datetime.now().isoformat(),
            "method": "heuristic"
        }

    @staticmethod
    def _error_result(message: str) -> Dict[str, Any]:
        return {
            "draft_file": "",
            "assignment_file": "",
            "audit_result": message,
            "missing_items": [],
            "formatting_issues": [],
            "coverage_score": 0,
            "audited_at": datetime.now().isoformat(),
            "method": "error"
        }

    @staticmethod
    def format_telegram_alert(audit: Dict[str, Any]) -> str:
        """Formats a rubric audit result as a Telegram message."""
        score = audit.get("coverage_score", 0)
        emoji = "🔴" if score < 50 else ("🟡" if score < 80 else "🟢")
        missing = audit.get("missing_items", [])
        fmt_issues = audit.get("formatting_issues", [])

        msg = (
            f"{emoji} *Pre-Submission Rubric Audit*\n"
            f"📄 File: `{audit.get('draft_file', 'Unknown')}`\n"
            f"📊 Coverage Score: *{score}/100*\n\n"
        )

        if missing:
            msg += "❌ *Missing Items:*\n"
            for item in missing[:5]:
                msg += f"  • {item}\n"

        if fmt_issues:
            msg += "\n⚠️ *Formatting Issues:*\n"
            for issue in fmt_issues[:3]:
                msg += f"  • {issue}\n"

        msg += f"\n💬 _{audit.get('audit_result', '')}_ "
        return msg.strip()
