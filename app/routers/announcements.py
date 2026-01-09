from fastapi import APIRouter, Depends, HTTPException, Security, Query
from sqlalchemy.orm import Session
from typing import List
from app import models, crud, schemas
from app.database import get_db
from app.core.security import get_current_active_superuser, get_current_active_user, audit_log

router = APIRouter(tags=["announcements"])

# ============= PUBLIC ENDPOINTS =============

@router.get("/announcements", response_model=schemas.AnnouncementListResponse)
def get_public_announcements(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    announcements = crud.get_announcements(db, skip=skip, limit=limit, published_only=True)
    total = crud.get_announcements_count(db, published_only=True)
    has_more = (skip + limit) < total

    return schemas.AnnouncementListResponse(
        announcements=announcements,
        total=total,
        has_more=has_more
    )

@router.get("/announcements/{announcement_id}", response_model=schemas.Announcement)
def get_public_announcement(
    announcement_id: int,
    db: Session = Depends(get_db)
):
    announcement = crud.get_announcement(db, announcement_id)

    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    if not announcement.is_published:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return announcement

# ============= ADMIN ENDPOINTS =============

@router.post("/admin/announcements", response_model=schemas.Announcement)
def create_announcement(
    announcement_data: schemas.AnnouncementCreate,
    current_user: models.User = Security(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    announcement = crud.create_announcement(
        db=db,
        announcement=announcement_data,
        created_by_id=current_user.id
    )

    crud.create_audit_log(
        db=db,
        action="announcement.created",
        user_id=current_user.id,
        resource_type="announcement",
        resource_id=str(announcement.id),
        details=f"Admin {current_user.username} created announcement '{announcement.title}'",
        success=True
    )

    audit_log(f"Admin {current_user.id} created announcement {announcement.id}")

    return announcement

@router.get("/admin/announcements", response_model=schemas.AnnouncementListResponse)
def get_all_announcements(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    published_only: bool = Query(False, description="Filter to show only published announcements"),
    current_user: models.User = Security(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    announcements = crud.get_announcements(db, skip=skip, limit=limit, published_only=published_only)
    total = crud.get_announcements_count(db, published_only=published_only)
    has_more = (skip + limit) < total

    audit_log(f"Admin {current_user.id} accessed announcements list")

    return schemas.AnnouncementListResponse(
        announcements=announcements,
        total=total,
        has_more=has_more
    )

@router.get("/admin/announcements/{announcement_id}", response_model=schemas.Announcement)
def get_announcement_admin(
    announcement_id: int,
    current_user: models.User = Security(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    announcement = crud.get_announcement(db, announcement_id)

    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    audit_log(f"Admin {current_user.id} accessed announcement {announcement_id}")

    return announcement

@router.put("/admin/announcements/{announcement_id}", response_model=schemas.Announcement)
def update_announcement(
    announcement_id: int,
    announcement_update: schemas.AnnouncementUpdate,
    current_user: models.User = Security(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    announcement = crud.get_announcement(db, announcement_id)

    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated_announcement = crud.update_announcement(
        db=db,
        announcement_id=announcement_id,
        announcement_update=announcement_update
    )

    crud.create_audit_log(
        db=db,
        action="announcement.updated",
        user_id=current_user.id,
        resource_type="announcement",
        resource_id=str(announcement_id),
        details=f"Admin {current_user.username} updated announcement '{announcement.title}'",
        success=True
    )

    audit_log(f"Admin {current_user.id} updated announcement {announcement_id}")

    return updated_announcement

@router.delete("/admin/announcements/{announcement_id}")
def delete_announcement(
    announcement_id: int,
    current_user: models.User = Security(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    announcement = crud.get_announcement(db, announcement_id)

    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")

    announcement_title = announcement.title

    success = crud.delete_announcement(db, announcement_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete announcement")

    crud.create_audit_log(
        db=db,
        action="announcement.deleted",
        user_id=current_user.id,
        resource_type="announcement",
        resource_id=str(announcement_id),
        details=f"Admin {current_user.username} deleted announcement '{announcement_title}'",
        success=True
    )

    audit_log(f"Admin {current_user.id} deleted announcement {announcement_id}")

    return {
        "message": f"Announcement '{announcement_title}' has been deleted",
        "id": announcement_id
    }