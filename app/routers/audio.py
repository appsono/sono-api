import uuid
import io
import logging
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path

from app.core.config import settings
from app.core.storage import minio_client
from app.core.security import get_current_active_superuser

from .. import crud, models, schemas
from ..dependencies import get_db, get_current_active_user

router = APIRouter(prefix="/audio", tags=["audio"])

ALLOWED_AUDIO_TYPES = ["audio/mpeg", "audio/mp3", "audio/wav", "audio/wave", "audio/ogg", "audio/m4a", "audio/aac", "audio/flac", "audio/webm", "audio/mp4", "application/octet-stream"]

MAX_AUDIO_SIZE = 50 * 1024 * 1024


@router.get("/stats", response_model=schemas.AudioUploadStats)
def get_upload_stats(current_user: models.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    stats = crud.get_user_upload_stats(db, current_user.id)
    return stats


@router.post("/upload", response_model=schemas.AudioFile)
async def upload_audio_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_public: bool = Form(False),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    can_upload, current_count, max_allowed = crud.can_user_upload_audio(db, current_user.id)
    if not can_upload:
        raise HTTPException(status_code=403, detail=f"Upload limit reached. You have {current_count} out of {max_allowed} audio files.")

    if file.content_type not in ALLOWED_AUDIO_TYPES:
        allowed_types_str = ", ".join([t.split("/")[1].upper() for t in ALLOWED_AUDIO_TYPES])
        raise HTTPException(status_code=400, detail=f"Unsupported audio format. Allowed formats: {allowed_types_str}")

    contents = await file.read()
    file_size = len(contents)

    if file_size > MAX_AUDIO_SIZE:
        max_size_mb = MAX_AUDIO_SIZE / (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {max_size_mb}MB")

    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    file_extension = Path(file.filename).suffix if file.filename else ".mp3"
    stored_filename = f"{uuid.uuid4()}{file_extension}"

    try:
        minio_client.put_object(bucket_name="audio-files", object_name=stored_filename, data=io.BytesIO(contents), length=file_size, content_type=file.content_type)

        file_url = f"{settings.minio_public_base}/audio-files/{stored_filename}"

        file_data = {
            "original_filename": file.filename or "untitled",
            "stored_filename": stored_filename,
            "title": title or file.filename or "untitled",
            "description": description,
            "file_size": file_size,
            "content_type": file.content_type,
            "file_url": file_url,
            "is_public": is_public,
        }

        db_file = crud.create_audio_file(db, file_data, current_user.id)

        return db_file

    except Exception as e:
        logging.error(f"Error uploading audio file to MinIO: {e}")
        raise HTTPException(status_code=500, detail="Could not upload file")


@router.get("/my-files", response_model=schemas.AudioFileListResponse)
def get_my_audio_files(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), current_user: models.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    files = crud.get_user_audio_files(db, current_user.id, skip=skip, limit=limit)
    total = crud.get_user_audio_files_count(db, current_user.id)
    has_more = (skip + limit) < total

    return {"files": files, "total": total, "has_more": has_more}


@router.get("/public", response_model=List[schemas.AudioFileResponse])
def get_public_audio_files(skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    files = crud.get_public_audio_files(db, skip=skip, limit=limit)
    return files


@router.get("/{file_id}", response_model=schemas.AudioFileResponse)
def get_audio_file(file_id: int, current_user: models.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    audio_file = crud.get_audio_file(db, file_id)
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    if audio_file.owner_id != current_user.id and not audio_file.is_public:
        raise HTTPException(status_code=403, detail="Access denied")

    return audio_file


@router.get("/{file_id}/download")
def download_audio_file(file_id: int, current_user: models.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    audio_file = crud.get_audio_file(db, file_id)
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    if audio_file.owner_id != current_user.id and not audio_file.is_public:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        response = minio_client.get_object("audio-files", audio_file.stored_filename)
        filename = audio_file.original_filename or f"{audio_file.title or 'audio'}{Path(audio_file.stored_filename).suffix}"

        from urllib.parse import quote

        ascii_filename = filename.encode("ascii", "replace").decode("ascii")
        utf8_filename = quote(filename)

        return StreamingResponse(
            response, media_type=audio_file.content_type or "application/octet-stream", headers={"Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}"}
        )
    except Exception as e:
        logging.error(f"Error downloading audio file from MinIO: {e}")
        raise HTTPException(status_code=500, detail="Could not download file")


@router.put("/{file_id}", response_model=schemas.AudioFile)
def update_audio_file(file_id: int, file_update: schemas.AudioFileUpdate, current_user: models.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    audio_file = crud.get_audio_file(db, file_id)
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    if audio_file.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only update your own files")

    updated_file = crud.update_audio_file(db, file_id, file_update)
    return updated_file


@router.delete("/{file_id}")
def delete_audio_file(file_id: int, current_user: models.User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    audio_file = crud.get_audio_file(db, file_id)
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    if audio_file.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You can only delete your own files")

    try:
        minio_client.remove_object("audio-files", audio_file.stored_filename)
    except Exception as e:
        logging.warning(f"Failed to delete file from MinIO: {e}")

    success = crud.delete_audio_file(db, file_id)
    if success:
        return {"message": "Audio file deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete file")


@router.get("/user/{user_id}/files", response_model=List[schemas.AudioFileResponse])
def admin_get_user_files(
    user_id: int, skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), current_user: models.User = Depends(get_current_active_superuser), db: Session = Depends(get_db)
):
    files = crud.get_user_audio_files(db, user_id, skip=skip, limit=limit)
    return files


@router.delete("/admin/{file_id}")
def admin_delete_audio_file(file_id: int, current_user: models.User = Depends(get_current_active_superuser), db: Session = Depends(get_db)):
    audio_file = crud.get_audio_file(db, file_id)
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")

    try:
        minio_client.remove_object("audio-files", audio_file.stored_filename)
    except Exception as e:
        logging.warning(f"Failed to delete file from MinIO: {e}")

    success = crud.delete_audio_file(db, file_id)
    if success:
        return {"message": f"Audio file {file_id} deleted by admin"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete file")
