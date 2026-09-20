from fastapi import UploadFile
from pypdf import PdfReader


def extract_text(upload: UploadFile) -> str:
    if upload.filename and upload.filename.lower().endswith(".pdf"):
        return "".join(page.extract_text() or "" for page in PdfReader(upload.file).pages)
    return upload.file.read().decode("utf-8", errors="replace")