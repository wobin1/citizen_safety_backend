import os
import re
import logging
from datetime import datetime, timedelta
from typing import Optional
from modules.shared.db import execute_query

try:
    import cloudinary
    import cloudinary.uploader
except Exception as cloud_err:  # Cloudinary optional import guard
    cloudinary = None  # type: ignore
    cloudinary_import_error = cloud_err
else:
    cloudinary_import_error = None

from fastapi import UploadFile
from starlette.concurrency import run_in_threadpool

def check_profanity(text: str) -> bool:
    """Simple profanity check using regex"""
    profanity_pattern = re.compile(r'\b(fuck|shit|ass|damn)\b', re.IGNORECASE)
    return bool(profanity_pattern.search(text))

async def check_duplicate(user_id: str, emergency_type: str, description: str, created_at: datetime) -> bool:
    """Check for duplicate emergencies"""
    time_window = created_at - timedelta(hours=1)
    query = """
    SELECT COUNT(*) 
    FROM emergency 
    WHERE user_id = $1 
    AND type = $2 
    AND description = $3
    AND created_at >= $4
    """
    result = await execute_query(query, (user_id, emergency_type, description, time_window))
    return result[0][0] > 0

def notify_emergency_services(emergency: dict):
    """Mock emergency service notification"""
    print(f"Mock: Notifying emergency services of {emergency['type']} (severity: {emergency['severity']}) at {emergency['location']}")

def notify_citizen(emergency_id: str, reason: str):
    """Mock citizen notification"""
    print(f"Mock: Notifying citizen of rejected emergency {emergency_id}: {reason}")


# -----------------------
# Cloudinary Upload Utils
# -----------------------

logger = logging.getLogger("emergency.utils")

def _ensure_cloudinary_configured() -> None:
    """Configure Cloudinary from env; raise informative error if missing."""
    if cloudinary is None:
        raise RuntimeError(
            f"cloudinary package not available: {cloudinary_import_error}. Install 'cloudinary' and try again."
        )

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not all([cloud_name, api_key, api_secret]):
        raise RuntimeError(
            "Cloudinary env vars missing. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET."
        )
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )

def _resource_type_for_mime(content_type: Optional[str]) -> str:
    if not content_type:
        return "auto"
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("video/") or content_type.startswith("audio/"):
        return "video"  # Cloudinary treats audio under video resource_type
    return "raw"

async def upload_media_to_cloudinary(
    file: UploadFile,
    folder: Optional[str] = None,
    overwrite: bool = False,
) -> str:
    """Upload a single file to Cloudinary and return the secure URL.

    - Auto-detects resource_type from MIME
    - Streams upload using the underlying file object
    - Runs the blocking uploader in a threadpool
    """
    _ensure_cloudinary_configured()
    resource_type = _resource_type_for_mime(file.content_type)
    upload_options = {
        "resource_type": resource_type,
        "use_filename": True,
        "unique_filename": True,
        "overwrite": overwrite,
    }
    if folder:
        upload_options["folder"] = folder

    async def _do_upload():
        return await run_in_threadpool(
            cloudinary.uploader.upload,  # type: ignore[attr-defined]
            file.file,
            **upload_options,
        )

    result = await _do_upload()
    secure_url = result.get("secure_url") or result.get("url")
    if not secure_url:
        raise RuntimeError("Cloudinary upload did not return a URL")
    logger.debug("Cloudinary upload successful: %s", secure_url)
    return secure_url

async def upload_optional_media(
    file: Optional[UploadFile],
    folder: Optional[str] = None,
) -> Optional[str]:
    """Upload optional file and return URL or None if no file provided."""
    if file is None:
        return None
    return await upload_media_to_cloudinary(file, folder=folder)