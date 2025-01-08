import os
import uuid
from fastapi import UploadFile
from pathlib import Path

UPLOAD_DIR = Path("app/static/uploads")

def save_upload_file(file: UploadFile, folder: str) -> str:
    """
    Save an uploaded file to the specified folder and return the file URL.
    """
    if not UPLOAD_DIR.exists():
        UPLOAD_DIR.mkdir(parents=True)

    # Create a unique filename
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = UPLOAD_DIR / folder / unique_filename

    # Create folder if it doesn't exist
    if not file_path.parent.exists():
        file_path.parent.mkdir(parents=True)

    with open(file_path, "wb") as buffer:
        buffer.write(file.file.read())

    return str(file_path)
