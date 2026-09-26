import re
import hashlib
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any
from bs4 import BeautifulSoup
from core.models import Course, AcademicActivity, ActivityType, SubmissionStatus, PriorityLevel

class OdoCustExtractor:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    # --- DASHBOARD PARSER ---
    def parse_dashboard_courses(self, html_content: str) -> List[Course]:
        """
        Parses enrolled courses from /student/dashboard or /student/course/info pages.
        Identifies course names, course codes, and unique course hash IDs.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        courses: Dict[str, Course] = {}

        # Look for course links matching /student/course/(info|outline|material|assessment|submission)/<hash>
        course_link_pattern = re.compile(r'/student/course/(?:info|outline|material|assessment|submission)/([A-Za-z0-9_-]+)')
        
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            match = course_link_pattern.search(href)
            if not match:
                continue

            course_hash = match.group(1)

            # First check if this anchor contains or is inside an Odoo card
            card = a_tag.find(class_="card") or a_tag.find_parent(class_="card")
            clean_name = ""
            instructor = ""
            code = ""
            attendance_pct = 100.0

            if card:
                header = card.find(class_="card-header")
                if header:
                    clean_name = header.get_text(strip=True)
                title = card.find(class_="card-title")
                if title:
                    instructor = title.get_text(strip=True)
                sub = card.find(class_="sub-heading")
                if sub:
                    code = sub.get_text(strip=True)
                
                # Extract attendance percentage
                card_text = card.get_text(" ", strip=True)
                att_match = re.search(r'Attendance:\s*([0-9]+(?:\.[0-9]+)?)\s*%', card_text, re.I)
                if att_match:
                    try:
                        attendance_pct = float(att_match.group(1))
                    except ValueError:
                        attendance_pct = 100.0

            if not clean_name:
                # Fallback to regex text parsing
                raw_text = a_tag.get_text(separator=" ", strip=True)
                tab_names = ["announcement", "news", "course outline", "course material", "assessments", "submission", "grade book", "attendance", "enrollments"]
                if raw_text.lower() in tab_names or len(raw_text) < 3:
                    continue
                code_match = re.search(r'\(([^)]*(?:SE|CS|EE|ME|BSE|BCS|BBA|\d{4})[^)]*)\)', raw_text, re.I)
                code = code_match.group(1).strip() if code_match else ""
                clean_name = re.sub(r'\((?:SE|CS|EE|ME|BSE|BCS|BBA|\d{4})[^)]*\)', '', raw_text).strip()
                clean_name = re.sub(r'\s+', ' ', clean_name)
                
                att_match = re.search(r'Attendance:\s*([0-9]+(?:\.[0-9]+)?)\s*%', raw_text, re.I)
                if att_match:
                    try:
                        attendance_pct = float(att_match.group(1))
                    except ValueError:
                        pass

            if not clean_name:
                clean_name = f"Course {course_hash[:6]}"

            full_url = f"{self.base_url}/student/course/info/{course_hash}"
            if course_hash not in courses:
                courses[course_hash] = Course(
                    course_id=course_hash,
                    name=clean_name,
                    code=code,
                    instructor=instructor,
                    url=full_url,
                    attendance_pct=attendance_pct,
                    last_synced=datetime.now()
                )

        return list(courses.values())

    # --- ANNOUNCEMENTS / NEWS PARSER ---
    def parse_announcements(self, html_content: str, course: Course) -> List[AcademicActivity]:
        """
        Parses announcements table from /student/course/info/<hash>
        Columns: Sr No., Subject, Date, Description, Attachment
        """
        soup = BeautifulSoup(html_content, "html.parser")
        activities: List[AcademicActivity] = []

        table = soup.find("table")
        if not table:
            # Fallback for card or list layout
            return self._parse_generic_cards(soup, course, ActivityType.ANNOUNCEMENT)

        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        
        # Map headers
        subject_idx = self._find_col_index(headers, ["subject", "title", "announcement", "news"])
        date_idx = self._find_col_index(headers, ["date", "posted", "created"])
        desc_idx = self._find_col_index(headers, ["description", "detail", "content"])
        attach_idx = self._find_col_index(headers, ["attachment", "file", "download"])

        tbody = table.find("tbody") or table
        rows = tbody.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if not cols:
                continue

            title = cols[subject_idx].get_text(strip=True) if subject_idx < len(cols) else ""
            if not title:
                continue

            date_str = cols[date_idx].get_text(strip=True) if date_idx < len(cols) else ""
            posted_date = self._parse_datetime(date_str)

            description = cols[desc_idx].get_text("\n", strip=True) if desc_idx < len(cols) else ""
            
            # Attachment link
            attach_url = ""
            attach_name = ""
            if attach_idx < len(cols):
                link_elem = cols[attach_idx].find("a", href=True)
                if link_elem:
                    attach_url = self._normalize_url(link_elem["href"])
                    attach_name = link_elem.get_text(strip=True) or "Attachment"

            # Detect activity type (e.g. if title says "Proposal", "Quiz", "Assignment")
            act_type = ActivityType.ANNOUNCEMENT
            title_lower = title.lower()
            if "quiz" in title_lower:
                act_type = ActivityType.QUIZ
            elif "project" in title_lower or "fyp" in title_lower:
                act_type = ActivityType.PROJECT
            elif "assignment" in title_lower:
                act_type = ActivityType.ASSIGNMENT

            # Extract any deadline mentioned inside description (e.g., "submit ... till 12 (noon) on Monday 28th Sept")
            deadline = self._extract_deadline_from_text(description)

            activity_id = self._generate_id(course.course_id, act_type.value, title, date_str)
            portal_url = f"{self.base_url}/student/course/info/{course.course_id}"

            activities.append(AcademicActivity(
                activity_id=activity_id,
                course_id=course.course_id,
                course_name=course.name,
                activity_type=act_type,
                title=title,
                description=description,
                posted_date=posted_date,
                deadline=deadline,
                submission_status=SubmissionStatus.UNKNOWN,
                attachment_url=attach_url,
                attachment_name=attach_name,
                portal_url=portal_url,
                last_checked_at=datetime.now()
            ))

        return activities

    # --- SUBMISSIONS / ASSIGNMENTS PARSER ---
    def parse_submissions(self, html_content: str, course: Course) -> List[AcademicActivity]:
        """
        Parses submissions table from /student/course/submission/<hash>
        Columns usually include: Sr No., Title/Task, Posted Date, Deadline, Status, Marks, Action
        """
        soup = BeautifulSoup(html_content, "html.parser")
        activities: List[AcademicActivity] = []

        table = soup.find("table")
        if not table:
            return self._parse_generic_cards(soup, course, ActivityType.ASSIGNMENT)

        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        
        title_idx = self._find_col_index(headers, ["title", "assignment", "project", "task", "subject"])
        posted_idx = self._find_col_index(headers, ["posted", "start", "assigned", "date"])
        deadline_idx = self._find_col_index(headers, ["deadline", "due", "submission date", "end date"])
        status_idx = self._find_col_index(headers, ["status", "submission status", "state"])
        marks_idx = self._find_col_index(headers, ["marks", "grade", "score", "weightage"])
        action_idx = self._find_col_index(headers, ["action", "submission", "submit", "upload", "file"])

        tbody = table.find("tbody") or table
        rows = tbody.find_all("tr")

        for row in rows:
            cols = row.find_all("td")
            if not cols:
                continue

            title = cols[title_idx].get_text(strip=True) if title_idx < len(cols) else ""
            if not title or title.lower() in ("no records", "no submissions found", "empty"):
                continue

            posted_str = cols[posted_idx].get_text(strip=True) if posted_idx < len(cols) else ""
            posted_date = self._parse_datetime(posted_str)

            deadline_str = cols[deadline_idx].get_text(strip=True) if deadline_idx < len(cols) else ""
            deadline = self._parse_datetime(deadline_str)

            status_str = cols[status_idx].get_text(strip=True) if status_idx < len(cols) else ""
            submission_status = self._parse_submission_status(status_str)

            marks = cols[marks_idx].get_text(strip=True) if marks_idx < len(cols) else ""

            # Check for direct file or action link
            attach_url = ""
            attach_name = ""
            if action_idx < len(cols):
                link = cols[action_idx].find("a", href=True)
                if link:
                    attach_url = self._normalize_url(link["href"])
                    attach_name = link.get_text(strip=True) or "Submission File"

            # Determine type
            act_type = ActivityType.ASSIGNMENT
            title_lower = title.lower()
            if any(k in title_lower for k in ["project", "fyp", "thesis", "capstone", "proposal"]):
                act_type = ActivityType.PROJECT
            elif any(k in title_lower for k in ["quiz", "test"]):
                act_type = ActivityType.QUIZ

            activity_id = self._generate_id(course.course_id, act_type.value, title, deadline_str or posted_str)
            portal_url = f"{self.base_url}/student/course/submission/{course.course_id}"

            activities.append(AcademicActivity(
                activity_id=activity_id,
                course_id=course.course_id,
                course_name=course.name,
                activity_type=act_type,
                title=title,
                posted_date=posted_date,
                deadline=deadline,
                submission_status=submission_status,
                marks=marks,
                attachment_url=attach_url,
                attachment_name=attach_name,
                portal_url=portal_url,
                last_checked_at=datetime.now()
            ))

        return activities

    # --- ASSESSMENTS / QUIZZES PARSER ---
    def parse_assessments(self, html_content: str, course: Course) -> List[AcademicActivity]:
        """
        Parses assessments / quizzes table from /student/course/assessment/<hash>
        """
        soup = BeautifulSoup(html_content, "html.parser")
        activities: List[AcademicActivity] = []

        table = soup.find("table")
        if not table:
            return activities

        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        title_idx = self._find_col_index(headers, ["assessment", "quiz", "title", "name"])
        date_idx = self._find_col_index(headers, ["date", "scheduled", "time", "deadline"])
        status_idx = self._find_col_index(headers, ["status", "result", "state"])
        marks_idx = self._find_col_index(headers, ["total marks", "marks", "weightage"])

        tbody = table.find("tbody") or table
        for row in tbody.find_all("tr"):
            cols = row.find_all("td")
            if not cols:
                continue
            title = cols[title_idx].get_text(strip=True) if title_idx < len(cols) else ""
            if not title:
                continue

            date_str = cols[date_idx].get_text(strip=True) if date_idx < len(cols) else ""
            deadline = self._parse_datetime(date_str)

            status_str = cols[status_idx].get_text(strip=True) if status_idx < len(cols) else ""
            submission_status = self._parse_submission_status(status_str)
            marks = cols[marks_idx].get_text(strip=True) if marks_idx < len(cols) else ""

            act_type = ActivityType.QUIZ
            if any(k in title.lower() for k in ["exam", "midterm", "final", "terminal"]):
                act_type = ActivityType.EXAM

            activity_id = self._generate_id(course.course_id, act_type.value, title, date_str)
            portal_url = f"{self.base_url}/student/course/assessment/{course.course_id}"

            activities.append(AcademicActivity(
                activity_id=activity_id,
                course_id=course.course_id,
                course_name=course.name,
                activity_type=act_type,
                title=title,
                deadline=deadline,
                submission_status=submission_status,
                marks=marks,
                portal_url=portal_url,
                last_checked_at=datetime.now()
            ))

        return activities

    # --- COURSE MATERIALS / PDFS PARSER ---
    def parse_materials(self, html_content: str, course: Course) -> List[AcademicActivity]:
        """
        Parses course materials (PDFs, lecture slides, files) from /student/course/material/<hash>
        """
        soup = BeautifulSoup(html_content, "html.parser")
        activities: List[AcademicActivity] = []

        table = soup.find("table")
        if table:
            headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            title_idx = self._find_col_index(headers, ["title", "material", "name", "subject", "topic"])
            date_idx = self._find_col_index(headers, ["date", "uploaded", "created"])
            desc_idx = self._find_col_index(headers, ["description", "detail"])
            file_idx = self._find_col_index(headers, ["file", "download", "attachment", "action"])

            tbody = table.find("tbody") or table
            for row in tbody.find_all("tr"):
                cols = row.find_all("td")
                if not cols:
                    continue
                title = cols[title_idx].get_text(strip=True) if title_idx < len(cols) else ""
                if not title:
                    continue

                date_str = cols[date_idx].get_text(strip=True) if date_idx < len(cols) else ""
                posted_date = self._parse_datetime(date_str)
                description = cols[desc_idx].get_text("\n", strip=True) if desc_idx < len(cols) else ""

                attach_url = ""
                attach_name = ""
                if file_idx < len(cols):
                    link = cols[file_idx].find("a", href=True)
                    if link:
                        attach_url = self._normalize_url(link["href"])
                        attach_name = link.get_text(strip=True) or "Download PDF/File"

                activity_id = self._generate_id(course.course_id, ActivityType.MATERIAL.value, title, date_str)
                portal_url = f"{self.base_url}/student/course/material/{course.course_id}"

                activities.append(AcademicActivity(
                    activity_id=activity_id,
                    course_id=course.course_id,
                    course_name=course.name,
                    activity_type=ActivityType.MATERIAL,
                    title=title,
                    description=description,
                    posted_date=posted_date,
                    submission_status=SubmissionStatus.UNKNOWN,
                    attachment_url=attach_url,
                    attachment_name=attach_name,
                    portal_url=portal_url,
                    last_checked_at=datetime.now()
                ))
        else:
            # Fallback for link lists or card layouts with pdf attachments
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if any(ext in href.lower() for ext in [".pdf", ".docx", ".pptx", ".zip", "/download/"]):
                    title = a_tag.get_text(strip=True) or "Course Material File"
                    attach_url = self._normalize_url(href)
                    activity_id = self._generate_id(course.course_id, ActivityType.MATERIAL.value, title, href)
                    activities.append(AcademicActivity(
                        activity_id=activity_id,
                        course_id=course.course_id,
                        course_name=course.name,
                        activity_type=ActivityType.MATERIAL,
                        title=title,
                        attachment_url=attach_url,
                        attachment_name=title,
                        portal_url=f"{self.base_url}/student/course/material/{course.course_id}",
                        last_checked_at=datetime.now()
                    ))

        return activities

    # --- HELPER UTILITIES ---
    def _find_col_index(self, headers: List[str], candidates: List[str]) -> int:
        for c in candidates:
            for idx, h in enumerate(headers):
                if c in h:
                    return idx
        return 999  # safe fallback

    def _normalize_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith("/"):
            return f"{self.base_url}{href}"
        if "odoo.cust.edu.pk" in href:
            return href.replace("https://odoo.cust.edu.pk", self.base_url).replace("http://odoo.cust.edu.pk", self.base_url)
        return href

    def _generate_id(self, course_id: str, act_type: str, title: str, date_hint: str) -> str:
        raw = f"{course_id}:{act_type}:{title.strip().lower()}:{date_hint.strip()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _parse_submission_status(self, text: str) -> SubmissionStatus:
        t = text.lower().strip()
        if any(w in t for w in ["submitted", "uploaded", "done", "completed", "received"]):
            if "late" in t:
                return SubmissionStatus.LATE_SUBMITTED
            return SubmissionStatus.SUBMITTED
        if any(w in t for w in ["not submitted", "pending", "unsubmitted", "missing", "due"]):
            return SubmissionStatus.NOT_SUBMITTED
        if any(w in t for w in ["graded", "checked", "evaluated"]):
            return SubmissionStatus.GRADED
        return SubmissionStatus.UNKNOWN

    def _parse_datetime(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        cleaned = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d-%m-%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %I:%M %p",
            "%d/%m/%Y",
            "%d %b %Y %I:%M %p",
            "%d %B %Y %I:%M %p",
            "%d %b %Y %H:%M",
            "%d %b %Y",
            "%d %B %Y",
            "%b %d, %Y",
            "%B %d, %Y"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
                
        # Try regex extract for YYYY-MM-DD
        m = re.search(r'(\d{4}-\d{2}-\d{2})', date_str)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y-%m-%d")
            except ValueError:
                pass

        return None

    def _extract_deadline_from_text(self, text: str) -> Optional[datetime]:
        """
        Attempts to extract deadlines mentioned in natural text, e.g.:
        "till 12 (noon) on Proposal defense day" or "deadline 2026-09-30"
        """
        m = re.search(r'deadline[:\s]+(\d{4}-\d{2}-\d{2})', text, re.I)
        if m:
            return self._parse_datetime(m.group(1))
        m2 = re.search(r'(\d{4}-\d{2}-\d{2})', text)
        if m2:
            return self._parse_datetime(m2.group(1))
        return None

    def _parse_generic_cards(self, soup: BeautifulSoup, course: Course, default_type: ActivityType) -> List[AcademicActivity]:
        activities = []
        cards = soup.find_all(class_=re.compile(r'card|list-group-item|item', re.I))
        for card in cards:
            title_elem = card.find(re.compile(r'h[1-6]|strong|b'))
            if not title_elem:
                continue
            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            desc = card.get_text("\n", strip=True)
            deadline = self._extract_deadline_from_text(desc)
            activity_id = self._generate_id(course.course_id, default_type.value, title, "")
            activities.append(AcademicActivity(
                activity_id=activity_id,
                course_id=course.course_id,
                course_name=course.name,
                activity_type=default_type,
                title=title,
                description=desc,
                deadline=deadline,
                submission_status=SubmissionStatus.UNKNOWN,
                portal_url=f"{self.base_url}/student/course/info/{course.course_id}",
                last_checked_at=datetime.now()
            ))
        return activities

    # --- ACADEMIC RESULTS & CGPA EXTRACTOR ---
    def parse_academic_results(self, html_content: str) -> Dict[str, Any]:
        """
        Parses semester-by-semester results and official cumulative GPA from /student/results.
        Returns a dict with:
        - current_cgpa: float
        - latest_sgpa: float
        - completed_credits: int
        - latest_term: str
        - terms: List[Dict[str, Any]] (All historical semesters with courses, GPAs, and credits)
        """
        soup = BeautifulSoup(html_content, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return {}

        table = tables[0]
        rows = table.find_all("tr")

        terms = []
        current_term = None

        for r in rows:
            tds = [td.get_text(strip=True) for td in r.find_all(["th", "td"])]
            if not tds:
                continue
            if len(tds) == 8 and tds[0] != "Term":
                try:
                    current_term = {
                        "term": tds[0],
                        "grade_points": float(tds[1]),
                        "cumulative_gp": float(tds[2]),
                        "attempted_ch": float(tds[3]),
                        "earned_ch": float(tds[4]),
                        "cumulative_ch": float(tds[5]),
                        "sgpa": float(tds[6]),
                        "cgpa": float(tds[7]),
                        "courses": []
                    }
                    terms.append(current_term)
                except Exception:
                    continue
            elif len(tds) == 4 and tds[0] != "Course" and current_term:
                try:
                    current_term["courses"].append({
                        "course": tds[0],
                        "credit_hours": float(tds[1]) if tds[1] else 0.0,
                        "grade_points": float(tds[2]) if tds[2] else 0.0,
                        "grade": tds[3]
                    })
                except Exception:
                    pass

        if not terms:
            return {}

        latest = terms[-1]
        return {
            "current_cgpa": float(latest["cgpa"]),
            "latest_sgpa": float(latest["sgpa"]),
            "completed_credits": int(round(latest["cumulative_ch"])),
            "latest_term": str(latest["term"]),
            "terms": terms
        }
