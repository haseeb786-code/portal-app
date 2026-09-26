import os
import re
import mimetypes
import logging
import urllib.parse
from typing import Optional
import requests

from core.models import AcademicActivity

logger = logging.getLogger("odocust.downloader")

class DocumentDownloader:
    def __init__(self, base_download_dir: str = "downloads"):
        self.base_download_dir = base_download_dir
        os.makedirs(self.base_download_dir, exist_ok=True)

    def download_activity_attachment(self, session: requests.Session, activity: AcademicActivity) -> Optional[str]:
        """
        Automatically downloads documents, PDFs, or files for an academic activity.
        Organizes files into:
        - downloads/FYP - Design Project/ (for FYP / Design Project items)
        - downloads/<Course Name>/ (for other subjects)
        
        Returns the relative local file path, or None if download fails / no attachment.
        """
        if not activity.attachment_url:
            return None

        # 1. Determine folder path
        if activity.is_fyp:
            folder_name = "FYP - Design Project"
        else:
            # Clean course name for folder
            folder_name = self._sanitize_filename(activity.course_name)
            if not folder_name:
                folder_name = f"Course_{activity.course_id[:8]}"

        target_dir = os.path.join(self.base_download_dir, folder_name)
        os.makedirs(target_dir, exist_ok=True)

        # Normalize domain to match active session host (tasjeel.cust.edu.pk)
        download_url = activity.attachment_url.replace("https://odoo.cust.edu.pk", "https://tasjeel.cust.edu.pk")

        try:
            logger.info(f"Initiating download for [{activity.title}] from {download_url}")
            res = session.get(download_url, stream=True, timeout=40, verify=False)
            if res.status_code != 200:
                logger.warning(f"Download failed with status {res.status_code} for URL: {download_url}")
                return None

            # Detect if response is actually a redirect to the login page
            content_type = res.headers.get("Content-Type", "").lower()
            if "text/html" in content_type and not activity.attachment_name.lower().endswith(".html"):
                peek = res.iter_content(chunk_size=1024)
                first_chunk = next(peek, b"")
                if b"login" in first_chunk.lower() or b"aarsol" in first_chunk.lower():
                    logger.warning(f"Download returned portal login HTML instead of file for {activity.title}. Check auth session.")
                    return None

            # 2. Extract filename from Content-Disposition header or fallback
            filename = self._extract_filename(res, activity)
            target_path = os.path.join(target_dir, filename)

            content_length = res.headers.get("Content-Length")
            expected_size = int(content_length) if content_length and content_length.isdigit() else None

            # 3. Deduplication check: Avoid re-downloading if identical file exists
            if os.path.exists(target_path):
                existing_size = os.path.getsize(target_path)
                if expected_size is not None and existing_size == expected_size and existing_size > 0:
                    logger.info(f"File already downloaded and matches expected size ({existing_size} bytes): {target_path}")
                    return target_path
                elif expected_size is None and existing_size > 0:
                    logger.info(f"File already exists ({existing_size} bytes): {target_path}")
                    return target_path

            # 4. Stream and save to disk
            with open(target_path, "wb") as f:
                if 'first_chunk' in locals() and first_chunk:
                    f.write(first_chunk)
                for chunk in res.iter_content(chunk_size=16384):
                    if chunk:
                        f.write(chunk)

            file_size = os.path.getsize(target_path)
            logger.info(f"✅ Successfully downloaded ({file_size} bytes) -> {target_path}")
            return target_path

        except Exception as e:
            logger.error(f"Error downloading attachment for activity '{activity.title}': {e}")
            return None

    def _extract_filename(self, response: requests.Response, activity: AcademicActivity) -> str:
        """
        Determines the cleanest and most accurate filename for a downloaded file.
        """
        # Try Content-Disposition
        cd = response.headers.get("Content-Disposition", "")
        if cd:
            # Handle filename*=UTF-8''...
            match_star = re.search(r"filename\*\s*=\s*(?:UTF-8'')?([^;\r\n]+)", cd, re.I)
            if match_star:
                fn = urllib.parse.unquote(match_star.group(1).strip().strip('"\''))
                if fn:
                    return self._sanitize_filename(fn)

            # Handle filename="..."
            match = re.search(r'filename\s*=\s*"?([^";\r\n]+)"?', cd, re.I)
            if match:
                fn = match.group(1).strip().strip('"\'')
                if fn:
                    return self._sanitize_filename(fn)

        # Fallback to activity.attachment_name if it looks like a real filename with extension
        if activity.attachment_name and "." in activity.attachment_name:
            return self._sanitize_filename(activity.attachment_name)

        # Fallback to title
        base_title = self._sanitize_filename(activity.title) or "document"
        
        # Guess extension from Content-Type
        content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
        ext = mimetypes.guess_extension(content_type) or ""
        if content_type == "application/zip":
            ext = ".zip"
        elif content_type == "application/pdf":
            ext = ".pdf"
        elif content_type in ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/msword"):
            ext = ".docx"

        if not base_title.endswith(ext):
            base_title += ext

        return base_title

    def _sanitize_filename(self, name: str) -> str:
        """
        Removes invalid characters for Windows and Unix filesystem compatibility.
        """
        if not name:
            return ""
        # Remove illegal filename chars
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name)
        # Collapse whitespace/underscores
        cleaned = re.sub(r'[\s_]+', ' ', cleaned).strip('. ')
        return cleaned[:150]
