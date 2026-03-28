import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import AuditAction, UploadType
from app.models.upload import Upload
from app.models.user import User
from app.services import audit_service

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _strip_exif(data: bytes, mime_type: str) -> bytes:
    """Strip EXIF metadata from image data using Pillow."""
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(data))

        # Create a clean copy without EXIF
        clean = Image.new(img.mode, img.size)
        clean.putdata(list(img.getdata()))

        output = io.BytesIO()
        fmt_map = {
            "image/jpeg": "JPEG",
            "image/png": "PNG",
            "image/webp": "WEBP",
        }
        fmt = fmt_map.get(mime_type, "JPEG")
        clean.save(output, format=fmt, quality=90)
        return output.getvalue()
    except Exception:
        logger.exception("Failed to strip EXIF data; returning original bytes")
        return data


# ---------------------------------------------------------------------------
# POST /image - Upload an image
# ---------------------------------------------------------------------------

@router.post("/image", status_code=status.HTTP_201_CREATED)
def upload_image(
    file: UploadFile = File(...),
    upload_type: UploadType = UploadType.photo,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Validate MIME type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type: {file.content_type}. Allowed: JPEG, PNG, WebP.",
        )

    # Read file data (use .file for sync access to SpooledTemporaryFile)
    data = file.file.read()

    # Validate file size
    max_bytes = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.MAX_IMAGE_SIZE_MB} MB.",
        )

    # Strip EXIF data
    data = _strip_exif(data, file.content_type)

    # Generate unique filename
    ext = ALLOWED_MIME_TYPES[file.content_type]
    unique_name = f"{uuid.uuid4().hex}{ext}"

    # Ensure upload directory exists
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save to disk
    file_path = upload_dir / unique_name
    file_path.write_bytes(data)

    # Create Upload record
    upload = Upload(
        uploaded_by=current_user.id,
        file_name=file.filename or unique_name,
        stored_path=str(file_path),
        mime_type=file.content_type,
        file_size=len(data),
        upload_type=upload_type,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    url = f"/uploads/{unique_name}"

    return {
        "id": str(upload.id),
        "url": url,
    }


# ---------------------------------------------------------------------------
# DELETE /{id} - Delete upload (owner or admin)
# ---------------------------------------------------------------------------

@router.delete("/{id}", response_model=dict)
def delete_upload(
    id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    upload = db.query(Upload).filter(Upload.id == id).first()
    if upload is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found",
        )

    # Only owner or admin can delete
    is_owner = upload.uploaded_by == current_user.id
    is_admin = current_user.role.value in ("admin", "system_admin")
    if not is_owner and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this upload",
        )

    # Delete file from disk
    try:
        file_path = Path(upload.stored_path)
        if file_path.exists():
            file_path.unlink()
    except Exception:
        logger.exception("Failed to delete file from disk: %s", upload.stored_path)

    # Delete record
    db.delete(upload)
    db.commit()

    return {"message": "Upload deleted"}
