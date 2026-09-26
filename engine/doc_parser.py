import os
import zipfile
import logging
from typing import Optional

logger = logging.getLogger("odocust.doc_parser")

class DocumentParser:
    """
    Safely parses academic attachments (PDF, DOCX, XLSX, TXT) and returns
    extracted text content for AI summarization.
    """

    @staticmethod
    def extract_text(file_path: str, max_chars: int = 15000) -> str:
        """
        Extracts up to max_chars of text from a given file path.
        Handles .pdf, .docx, .xlsx, .txt, and extracts zip if compressed.
        """
        if not file_path or not os.path.exists(file_path):
            return ""

        ext = os.path.splitext(file_path)[1].lower()

        try:
            # Handle zipped attachments (e.g. .xlsx.zip)
            if ext == ".zip":
                return DocumentParser._extract_from_zip(file_path, max_chars)

            if ext == ".pdf":
                return DocumentParser._extract_from_pdf(file_path, max_chars)

            elif ext in (".docx", ".doc"):
                return DocumentParser._extract_from_docx(file_path, max_chars)

            elif ext in (".xlsx", ".xls"):
                return DocumentParser._extract_from_xlsx(file_path, max_chars)

            elif ext in (".txt", ".md", ".py", ".sql", ".json", ".csv"):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read(max_chars)

            else:
                logger.info(f"Unrecognized document format '{ext}' for text extraction: {file_path}")
                return ""

        except Exception as e:
            logger.warning(f"Failed to extract text from {file_path}: {e}")
            return ""

    @staticmethod
    def _extract_from_pdf(file_path: str, max_chars: int) -> str:
        import pypdf
        text_parts = []
        total_len = 0
        reader = pypdf.PdfReader(file_path)
        for page_idx, page in enumerate(reader.pages):
            txt = page.extract_text() or ""
            text_parts.append(txt)
            total_len += len(txt)
            if total_len >= max_chars:
                break
        return "\n".join(text_parts)[:max_chars]

    @staticmethod
    def _extract_from_docx(file_path: str, max_chars: int) -> str:
        import docx
        doc = docx.Document(file_path)
        text_parts = []
        total_len = 0
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                text_parts.append(txt)
                total_len += len(txt)
            if total_len >= max_chars:
                break
        return "\n".join(text_parts)[:max_chars]

    @staticmethod
    def _extract_from_xlsx(file_path: str, max_chars: int) -> str:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        text_parts = []
        total_len = 0

        for sheet_name in wb.sheetnames[:3]:  # First 3 sheets max
            sheet = wb[sheet_name]
            text_parts.append(f"--- Sheet: {sheet_name} ---")
            row_count = 0
            for row in sheet.iter_rows(values_only=True):
                # Filter None values
                row_vals = [str(v).strip() for v in row if v is not None and str(v).strip()]
                if row_vals:
                    line = " | ".join(row_vals)
                    text_parts.append(line)
                    total_len += len(line)
                    row_count += 1
                if total_len >= max_chars or row_count > 60:
                    break
            if total_len >= max_chars:
                break
        wb.close()
        return "\n".join(text_parts)[:max_chars]

    @staticmethod
    def _extract_from_zip(file_path: str, max_chars: int) -> str:
        """Extracts text from the first readable document inside a zip archive."""
        with zipfile.ZipFile(file_path, 'r') as z:
            namelist = z.namelist()
            for name in namelist:
                sub_ext = os.path.splitext(name)[1].lower()
                if sub_ext in ('.pdf', '.docx', '.xlsx', '.txt', '.csv'):
                    # Extract to temp in memory or temp file
                    extracted_path = z.extract(name, path=os.path.dirname(file_path))
                    try:
                        return DocumentParser.extract_text(extracted_path, max_chars)
                    finally:
                        if os.path.exists(extracted_path) and extracted_path != file_path:
                            try:
                                os.remove(extracted_path)
                            except Exception:
                                pass
        return ""
