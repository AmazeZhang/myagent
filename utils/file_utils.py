# utils/file_utils.py
import os, uuid
from pathlib import Path
from typing import Tuple

UPLOAD_DIR = Path("assets/uploads")
SCREENSHOT_DIR = Path("assets/screenshots")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

def ensure_dirs():
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

def save_upload(file_obj, filename: str = None) -> Tuple[str, str]:
    """
    Save a Streamlit uploaded file-like object to assets/uploads and return (doc_id, path).
    """
    ensure_dirs()
    if filename is None:
        filename = getattr(file_obj, "name", f"upload-{uuid.uuid4().hex}")
    # sanitize filename
    filename = Path(filename).name
    unique = f"{uuid.uuid4().hex}_{filename}"
    target = UPLOAD_DIR / unique
    with open(target, "wb") as f:
        f.write(file_obj.getbuffer() if hasattr(file_obj, "getbuffer") else file_obj.read())
    doc_id = unique  # doc_id uses filename prefix + uuid
    return doc_id, str(target)

def make_path_for_output(basename: str) -> str:
    ensure_dirs()
    safe = Path(basename).name
    out = UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe}"
    return str(out)

def screenshot_path(name: str) -> str:
    ensure_dirs()
    return str(SCREENSHOT_DIR / f"{uuid.uuid4().hex}_{Path(name).name}.png")
