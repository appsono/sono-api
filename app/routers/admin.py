from fastapi import APIRouter, Depends, HTTPException, Security, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app import models, crud, schemas
from app.database import get_db
from app.core.security import get_current_active_superuser, audit_log
from app.core.storage import minio_client

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/collections/stats", response_model=schemas.CollectionStats)
def get_collection_stats(
    current_user: models.User = Security(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    audit_log(f"Collection stats accessed by admin {current_user.id}")
    stats = crud.get_collection_stats(db)
    return stats

@router.get("/users/{user_id}/collections/stats", response_model=schemas.UserCollectionStats)
def get_user_collection_stats(
    user_id: int,
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    audit_log(f"User {user_id} collection stats accessed by admin {current_user.id}")
    stats = crud.get_collection_stats(db, user_id=user_id)
    
    return schemas.UserCollectionStats(
        user_id=user_id,
        username=user.username,
        **stats
    )

@router.delete("/users/{user_id}/collections/all")
def delete_all_user_collections(
    user_id: int,
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_collections = crud.get_collections(db, owner_id=user_id, skip=0, limit=10000)
    
    deleted_count = 0
    failed_count = 0
    deleted_by_type = {"album": 0, "playlist": 0, "compilation": 0}
    
    try:
        for collection in user_collections:
            try:
                if collection.cover_art_url:
                    try:
                        filename = collection.cover_art_url.split("/")[-1]
                        minio_client.remove_object("cover-art", filename)
                    except:
                        pass
                
                if crud.delete_collection(db, collection.id):
                    deleted_count += 1
                    deleted_by_type[collection.collection_type] += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                continue
    
    except Exception as e:
        audit_log(f"Error deleting collections for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting collections: {str(e)}")
    
    audit_log(
        f"Admin {current_user.id} deleted all collections for user {user_id}: "
        f"{deleted_by_type['album']} albums, {deleted_by_type['compilation']} compilations, "
        f"{deleted_by_type['playlist']} playlists ({failed_count} failed)"
    )
    
    return {
        "message": f"Deleted {deleted_count} collections total",
        "deleted_albums": deleted_by_type["album"],
        "deleted_compilations": deleted_by_type["compilation"],
        "deleted_playlists": deleted_by_type["playlist"],
        "failed": failed_count,
        "total_processed": len(user_collections)
    }

@router.get("/collections/recent", response_model=dict)
def get_recent_collections(
    limit: int = Query(20, ge=1, le=100),
    collection_type: Optional[schemas.CollectionType] = Query(None),
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    recent = crud.get_recent_collections(db, limit=limit, collection_type=collection_type)

    audit_log(f"Recent collections accessed by admin {current_user.id}")

    collections_by_type = {"album": [], "playlist": [], "compilation": []}
    serialized = []

    for c in recent:
        data = {
            "id": c.id,
            "title": c.title,
            "owner_id": c.owner_id,
            "owner_username": c.owner.username if c.owner else None,
            "created_date": c.created_date,
            "is_public": c.is_public,
            "is_collaborative": c.is_collaborative,
            "track_count": len(c.tracks)
        }

        if c.collection_type == "album" and c.artist:
            data["artist"] = c.artist
        elif c.collection_type == "compilation" and c.curator_note:
            note = c.curator_note
            data["curator_note"] = note[:100] + "..." if len(note) > 100 else note

        collections_by_type[c.collection_type].append(data)
        serialized.append(data)

    return {
        "recent_collections": serialized,
        "by_type": collections_by_type,
        "filter_applied": collection_type.value if collection_type else None,
        "total_returned": len(serialized),
    }

@router.get("/collections/summary", response_model=dict)
def get_collections_summary(
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    stats = crud.get_collection_stats(db)
    
    top_creators = db.query(
        models.User.id,
        models.User.username,
        func.count(models.Collection.id).label('collection_count')
    ).join(models.Collection).group_by(
        models.User.id, models.User.username
    ).order_by(
        func.count(models.Collection.id).desc()
    ).limit(10).all()
    
    most_collaborative = db.query(models.Collection).options(
        joinedload(models.Collection.owner)
    ).filter(
        models.Collection.is_collaborative == True
    ).order_by(
        models.Collection.created_date.desc()
    ).limit(10).all()
    
    largest_collections = db.query(
        models.Collection.id,
        models.Collection.title,
        models.Collection.collection_type,
        models.User.username,
        func.count(models.CollectionTrack.id).label('track_count')
    ).join(models.User).outerjoin(models.CollectionTrack).group_by(
        models.Collection.id,
        models.Collection.title,
        models.Collection.collection_type,
        models.User.username
    ).order_by(
        func.count(models.CollectionTrack.id).desc()
    ).limit(10).all()
    
    audit_log(f"Collections summary accessed by admin {current_user.id}")
    
    return {
        "stats": stats,
        "top_creators": [
            {
                "user_id": creator.id,
                "username": creator.username,
                "collection_count": creator.collection_count
            } for creator in top_creators
        ],
        "most_collaborative": [
            {
                "id": collection.id,
                "title": collection.title,
                "type": collection.collection_type,
                "owner": collection.owner.username,
                "collaborator_count": len(collection.collaborators),
                "created_date": collection.created_date
            } for collection in most_collaborative
        ],
        "largest_collections": [
            {
                "id": collection.id,
                "title": collection.title,
                "type": collection.collection_type,
        "owner": collection.username,
                "track_count": collection.track_count
            } for collection in largest_collections
        ]
    }

@router.get("/stats", response_model=schemas.AdminStats)
def get_stats(
    current_user: models.User = Security(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    audit_log(f"Stats accessed by admin {current_user.id}")
    
    user_stats = {
        "total_users": db.query(models.User).count(),
        "active_users": db.query(models.User).filter(models.User.is_active == True).count(),
        "inactive_users": db.query(models.User).filter(models.User.is_active == False).count(),
        "superusers": db.query(models.User).filter(models.User.is_superuser == True).count(),
        "total_audio_files": db.query(models.AudioFile).count()
    }

    collection_stats = crud.get_collection_stats(db)

    comprehensive_stats = {
        **user_stats,
        **collection_stats
    }
    
    return comprehensive_stats

@router.get("/users", response_model=List[schemas.User])
def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    audit_log(f"User list accessed by admin {current_user.id}")
    
    users = crud.get_users(db, skip=skip, limit=limit)
    
    for user in users:
        audio_file_count = db.query(models.AudioFile).filter(
            models.AudioFile.owner_id == user.id
        ).count()
        user.total_audio_files = audio_file_count
    
    return users

@router.get("/users/{user_id}", response_model=schemas.User)
def get_user_details(
    user_id: int,
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    audit_log(f"User {user_id} details accessed by admin {current_user.id}")
    return user

@router.put("/users/{user_id}/upload-limit", response_model=schemas.User)
def update_user_upload_limit(
    user_id: int,
    limit_update: schemas.UserUploadLimitUpdate,
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_superuser and user_id != current_user.id:
        raise HTTPException(
            status_code=400, 
            detail="Cannot modify upload limits for other superusers"
        )
    
    updated_user = crud.update_user_upload_limit(db, user_id, limit_update.max_audio_uploads)
    
    if updated_user:
        audit_log(
            f"Admin {current_user.id} updated user {user_id} upload limit to {limit_update.max_audio_uploads}"
        )
        return updated_user
    else:
        raise HTTPException(status_code=500, detail="Failed to update upload limit")

@router.get("/users/{user_id}/upload-stats", response_model=schemas.AudioUploadStats)
def get_user_upload_stats(
    user_id: int,
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    stats = crud.get_user_upload_stats(db, user_id)
    return stats

@router.get("/audio-files/all", response_model=List[schemas.AudioFileResponse])
def get_all_audio_files(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    audio_files = (
        db.query(models.AudioFile)
        .order_by(models.AudioFile.upload_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    
    audit_log(f"All audio files accessed by admin {current_user.id}")
    return audio_files

@router.delete("/users/{user_id}/audio-files")
def delete_all_user_audio_files(
    user_id: int,
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_files = crud.get_user_audio_files(db, user_id, skip=0, limit=1000)
    
    deleted_count = 0
    failed_count = 0
    
    for audio_file in user_files:
        try:
            from app.core.storage import minio_client
            minio_client.remove_object("audio-files", audio_file.stored_filename)
        except Exception as e:
            failed_count += 1
            continue
        
        if crud.delete_audio_file(db, audio_file.id):
            deleted_count += 1
        else:
            failed_count += 1
    
    audit_log(
        f"Admin {current_user.id} deleted {deleted_count} audio files for user {user_id} "
        f"({failed_count} failed)"
    )
    
    return {
        "message": f"Deleted {deleted_count} audio files",
        "failed": failed_count,
        "total_processed": len(user_files)
    }

@router.post("/users/{user_id}/reset-uploads")
def reset_user_uploads(
    user_id: int,
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_superuser and user_id != current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot reset uploads for other superusers"
        )

    user_files = crud.get_user_audio_files(db, user_id, skip=0, limit=1000)

    deleted_count = 0
    for audio_file in user_files:
        try:
            from app.core.storage import minio_client
            minio_client.remove_object("audio-files", audio_file.stored_filename)
        except:
            pass

        if crud.delete_audio_file(db, audio_file.id):
            deleted_count += 1

    crud.update_user_upload_limit(db, user_id, 20)

    audit_log(
        f"Admin {current_user.id} reset uploads for user {user_id}: "
        f"deleted {deleted_count} files, reset limit to 20"
    )

    return {
        "message": f"Reset complete: deleted {deleted_count} files and reset limit to 20",
        "files_deleted": deleted_count
    }

@router.post("/users/{user_id}/disable")
def disable_user(
    user_id: int,
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_superuser and user_id != current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot disable other superusers"
        )

    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot disable your own account"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=400,
            detail="User is already disabled"
        )

    user.is_active = False
    db.commit()

    crud.create_audit_log(
        db=db,
        action="user.disabled",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(user_id),
        details=f"Admin {current_user.username} disabled user {user.username} (ID: {user_id})",
        success=True
    )

    audit_log(f"Admin {current_user.id} disabled user {user_id} ({user.username})")

    return {
        "message": f"User {user.username} has been disabled",
        "user_id": user_id,
        "username": user.username,
        "is_active": user.is_active
    }

@router.post("/users/{user_id}/enable")
def enable_user(
    user_id: int,
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_active:
        raise HTTPException(
            status_code=400,
            detail="User is already enabled"
        )

    user.is_active = True
    db.commit()

    crud.create_audit_log(
        db=db,
        action="user.enabled",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(user_id),
        details=f"Admin {current_user.username} enabled user {user.username} (ID: {user_id})",
        success=True
    )

    audit_log(f"Admin {current_user.id} enabled user {user_id} ({user.username})")

    return {
        "message": f"User {user.username} has been enabled",
        "user_id": user_id,
        "username": user.username,
        "is_active": user.is_active
    }

@router.post("/process-pending-deletions")
def process_pending_deletions_endpoint(
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    """Manually trigger processing of pending account deletions (for testing/debugging)"""
    from app.tasks.data_retention import process_pending_deletions

    audit_log(f"Admin {current_user.id} manually triggered pending deletion processing")

    processed_count = process_pending_deletions(db)

    return {
        "message": f"Processed {processed_count} pending deletions",
        "processed_count": processed_count
    }


@router.post("/cleanup-profile-pictures")
def cleanup_profile_pictures_endpoint(
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    from app.tasks.data_retention import cleanup_unused_profile_pictures

    crud.create_audit_log(
        db=db,
        action="admin.cleanup_profile_pictures",
        user_id=current_user.id,
        resource_type="storage",
        resource_id="profile-pictures",
        details=f"Admin {current_user.username} triggered profile picture cleanup",
        success=True
    )

    audit_log(f"Admin {current_user.id} manually triggered profile picture cleanup")

    result = cleanup_unused_profile_pictures(db)

    return {
        "message": "Profile picture cleanup complete",
        "deleted_count": result.get("deleted", 0),
        "error_count": result.get("errors", 0)
    }


@router.post("/run-all-cleanup-tasks")
def run_all_cleanup_tasks_endpoint(
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    from app.tasks.data_retention import (
        cleanup_expired_revoked_tokens,
        process_pending_deletions,
        cleanup_old_audit_logs,
        cleanup_unused_profile_pictures,
        initialize_default_retention_policies
    )

    crud.create_audit_log(
        db=db,
        action="admin.run_all_cleanup_tasks",
        user_id=current_user.id,
        resource_type="system",
        resource_id="cleanup",
        details=f"Admin {current_user.username} triggered all cleanup tasks",
        success=True
    )

    audit_log(f"Admin {current_user.id} manually triggered all cleanup tasks")

    results = {
        "expired_tokens_cleaned": cleanup_expired_revoked_tokens(db),
        "pending_deletions_processed": process_pending_deletions(db),
        "old_audit_logs_cleaned": cleanup_old_audit_logs(db, retention_days=3650),
        "profile_pictures_cleanup": cleanup_unused_profile_pictures(db),
        "retention_policies_initialized": True
    }

    initialize_default_retention_policies(db)

    return {
        "message": "All cleanup tasks completed",
        "results": results
    }


@router.get("/scheduled-jobs")
def get_scheduled_jobs_endpoint(
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    from app.core.scheduler import get_scheduled_jobs

    audit_log(f"Admin {current_user.id} viewed scheduled jobs")

    jobs = get_scheduled_jobs()

    return {
        "message": "Scheduled jobs retrieved",
        "jobs": jobs,
        "total_jobs": len(jobs)
    }