from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func
from . import models, schemas
from typing import Optional, List, Tuple
from core.hashing import Hasher

# ============= USER CRUD =============

def get_user(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.User).offset(skip).limit(limit).all()

def get_system_stats(db: Session):
    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(models.User.is_active == True).count()
    inactive_users = db.query(models.User).filter(models.User.is_active == False).count()
    superusers = db.query(models.User).filter(models.User.is_superuser == True).count()
    total_audio_files = db.query(models.AudioFile).count()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "superusers": superusers,
        "total_audio_files": total_audio_files,
    }

def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = Hasher.get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password,
        username=user.username,
        display_name=user.display_name,
        max_audio_uploads=20
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, identifier: str, password: str) -> Optional[models.User]:
    user = get_user_by_username(db, username=identifier)
    if not user:
        user = get_user_by_email(db, email=identifier)
    if not user:
        return None

    #check if user account is active
    if not user.is_active:
        return None

    if not Hasher.verify_password(password, user.hashed_password):
        return None
    return user

def update_user_upload_limit(db: Session, user_id: int, max_uploads: int) -> Optional[models.User]:
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.max_audio_uploads = max_uploads
        db.commit()
        db.refresh(user)
    return user

# ============= AUDIO FILE CRUD =============

def get_audio_file(db: Session, file_id: int) -> Optional[models.AudioFile]:
    return db.query(models.AudioFile).filter(models.AudioFile.id == file_id).first()

def get_audio_file_by_stored_filename(db: Session, stored_filename: str) -> Optional[models.AudioFile]:
    return db.query(models.AudioFile).filter(models.AudioFile.stored_filename == stored_filename).first()

def get_user_audio_files(
    db: Session, 
    user_id: int, 
    skip: int = 0, 
    limit: int = 100,
    include_public_only: bool = False
) -> List[models.AudioFile]:
    query = db.query(models.AudioFile).filter(models.AudioFile.owner_id == user_id)
    
    if include_public_only:
        query = query.filter(models.AudioFile.is_public == True)
    
    return query.offset(skip).limit(limit).all()

def get_user_audio_files_count(db: Session, user_id: int) -> int:
    return db.query(models.AudioFile).filter(models.AudioFile.owner_id == user_id).count()

def get_public_audio_files(db: Session, skip: int = 0, limit: int = 100) -> List[models.AudioFile]:
    return (
        db.query(models.AudioFile)
        .filter(models.AudioFile.is_public == True)
        .order_by(models.AudioFile.upload_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def create_audio_file(db: Session, file_data: dict, owner_id: int) -> models.AudioFile:
    db_file = models.AudioFile(
        original_filename=file_data["original_filename"],
        stored_filename=file_data["stored_filename"],
        title=file_data.get("title"),
        description=file_data.get("description"),
        file_size=file_data["file_size"],
        duration=file_data.get("duration"),
        content_type=file_data["content_type"],
        file_url=file_data["file_url"],
        is_public=file_data.get("is_public", False),
        owner_id=owner_id
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)
    return db_file

def update_audio_file(
    db: Session, 
    file_id: int, 
    update_data: schemas.AudioFileUpdate
) -> Optional[models.AudioFile]:
    db_file = db.query(models.AudioFile).filter(models.AudioFile.id == file_id).first()
    if db_file:
        update_dict = update_data.dict(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(db_file, key, value)
        db.commit()
        db.refresh(db_file)
    return db_file

def delete_audio_file(db: Session, file_id: int) -> bool:
    db_file = db.query(models.AudioFile).filter(models.AudioFile.id == file_id).first()
    if db_file:
        db.query(models.CollectionTrack).filter(
            models.CollectionTrack.audio_file_id == file_id
        ).delete()
        db.delete(db_file)
        db.commit()
        return True
    return False

def can_user_upload_audio(db: Session, user_id: int) -> tuple[bool, int, int]:
    user = get_user(db, user_id)
    if not user:
        return False, 0, 0
    
    current_count = get_user_audio_files_count(db, user_id)
    
    #superusers have no limits
    if user.is_superuser:
        return True, current_count, -1  #-1 indicates unlimited
    
    return current_count < user.max_audio_uploads, current_count, user.max_audio_uploads

def get_user_upload_stats(db: Session, user_id: int) -> dict:
    user = get_user(db, user_id)
    if not user:
        return {"error": "User not found"}
    
    current_count = get_user_audio_files_count(db, user_id)
    max_uploads = -1 if user.is_superuser else user.max_audio_uploads
    remaining = -1 if user.is_superuser else max(0, user.max_audio_uploads - current_count)
    
    return {
        "used_uploads": current_count,
        "max_uploads": max_uploads,
        "remaining_uploads": remaining
    }

# ============= COLLECTION CRUD =============

def get_collection(db: Session, collection_id: int) -> Optional[models.Collection]:
    return db.query(models.Collection).options(
        joinedload(models.Collection.owner),
        joinedload(models.Collection.tracks).joinedload(models.CollectionTrack.audio_file),
        joinedload(models.Collection.collaborators).joinedload(models.CollectionCollaborator.user)
    ).filter(models.Collection.id == collection_id).first()

def get_collections(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    owner_id: Optional[int] = None,
    collection_type: Optional[schemas.CollectionType] = None,
    public_only: bool = False,
    collaborative_only: bool = False
) -> List[models.Collection]:
    query = db.query(models.Collection).options(joinedload(models.Collection.owner))
    
    if owner_id:
        query = query.filter(models.Collection.owner_id == owner_id)
    if collection_type:
        query = query.filter(models.Collection.collection_type == collection_type)
    if public_only:
        query = query.filter(models.Collection.is_public == True)
    if collaborative_only:
        query = query.filter(models.Collection.is_collaborative == True)
    
    return query.order_by(models.Collection.created_date.desc()).offset(skip).limit(limit).all()

def get_collections_count(
    db: Session,
    owner_id: Optional[int] = None,
    collection_type: Optional[schemas.CollectionType] = None,
    public_only: bool = False
) -> int:
    query = db.query(models.Collection)
    
    if owner_id:
        query = query.filter(models.Collection.owner_id == owner_id)
    if collection_type:
        query = query.filter(models.Collection.collection_type == collection_type)
    if public_only:
        query = query.filter(models.Collection.is_public == True)
    
    return query.count()

def create_collection(db: Session, collection: schemas.CollectionCreate, owner_id: int) -> models.Collection:
    db_collection = models.Collection(
        title=collection.title,
        description=collection.description,
        collection_type=collection.collection_type,
        artist=collection.artist,
        curator_note=collection.curator_note,
        is_public=collection.is_public,
        is_collaborative=collection.is_collaborative,
        owner_id=owner_id
    )
    db.add(db_collection)
    db.commit()
    db.refresh(db_collection)
    return db_collection

def update_collection(db: Session, collection_id: int, collection_update: schemas.CollectionUpdate) -> Optional[models.Collection]:
    db_collection = db.query(models.Collection).filter(models.Collection.id == collection_id).first()
    if db_collection:
        update_dict = collection_update.dict(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(db_collection, key, value)
        db.commit()
        db.refresh(db_collection)
    return db_collection

def delete_collection(db: Session, collection_id: int) -> bool:
    db_collection = db.query(models.Collection).filter(models.Collection.id == collection_id).first()
    if db_collection:
        db.delete(db_collection)
        db.commit()
        return True
    return False

# ============= COLLECTION TRACK CRUD =============

def add_track_to_collection(
    db: Session, 
    collection_id: int, 
    track_data: schemas.CollectionTrackCreate, 
    added_by_id: int
) -> Optional[models.CollectionTrack]:
    
    #get next track order if not specified
    if track_data.track_order is None:
        max_order = db.query(func.max(models.CollectionTrack.track_order)).filter(
            models.CollectionTrack.collection_id == collection_id
        ).scalar()
        track_order = (max_order or 0) + 1
    else:
        track_order = track_data.track_order
        #shift existing tracks if needed
        db.query(models.CollectionTrack).filter(
            and_(models.CollectionTrack.collection_id == collection_id,
                 models.CollectionTrack.track_order >= track_order)
        ).update({models.CollectionTrack.track_order: models.CollectionTrack.track_order + 1})
    
    db_track = models.CollectionTrack(
        collection_id=collection_id,
        audio_file_id=track_data.audio_file_id,
        track_order=track_order,
        added_by_id=added_by_id
    )
    db.add(db_track)
    db.commit()
    db.refresh(db_track)
    return db_track

def remove_track_from_collection(db: Session, collection_id: int, track_id: int) -> bool:
    db_track = db.query(models.CollectionTrack).filter(
        and_(models.CollectionTrack.collection_id == collection_id, 
             models.CollectionTrack.id == track_id)
    ).first()
    if db_track:
        old_order = db_track.track_order
        db.delete(db_track)
        
        #shift remaining tracks up to fill gap
        db.query(models.CollectionTrack).filter(
            and_(models.CollectionTrack.collection_id == collection_id,
                 models.CollectionTrack.track_order > old_order)
        ).update({models.CollectionTrack.track_order: models.CollectionTrack.track_order - 1})
        
        db.commit()
        return True
    return False

def reorder_collection_track(db: Session, collection_id: int, track_id: int, new_order: int) -> Optional[models.CollectionTrack]:
    track = db.query(models.CollectionTrack).filter(
        and_(models.CollectionTrack.collection_id == collection_id,
             models.CollectionTrack.id == track_id)
    ).first()
    if not track:
        return None

    old_order = track.track_order

    if new_order == old_order:
        return track

    #temporarily move the track out of the way to avoid conflicts
    track.track_order = -1
    db.flush()

    if new_order > old_order:
        #moving down - shift tracks up (decrement)
        tracks_to_shift = db.query(models.CollectionTrack).filter(
            and_(models.CollectionTrack.collection_id == collection_id,
                 models.CollectionTrack.track_order > old_order,
                 models.CollectionTrack.track_order <= new_order)
        ).order_by(models.CollectionTrack.track_order.asc()).all()
        for t in tracks_to_shift:
            t.track_order -= 1
            db.flush()
    else:
        #moving up - shift tracks down (increment)
        tracks_to_shift = db.query(models.CollectionTrack).filter(
            and_(models.CollectionTrack.collection_id == collection_id,
                 models.CollectionTrack.track_order >= new_order,
                 models.CollectionTrack.track_order < old_order)
        ).order_by(models.CollectionTrack.track_order.desc()).all()
        for t in tracks_to_shift:
            t.track_order += 1
            db.flush()

    #update the track's position
    track.track_order = new_order
    db.commit()
    db.refresh(track)
    return track

def bulk_add_tracks_to_collection(
    db: Session,
    collection_id: int,
    audio_file_ids: List[int],
    added_by_id: int
) -> List[models.CollectionTrack]:
    #get starting order
    max_order = db.query(func.max(models.CollectionTrack.track_order)).filter(
        models.CollectionTrack.collection_id == collection_id
    ).scalar()
    start_order = (max_order or 0) + 1
    
    added_tracks = []
    for i, audio_file_id in enumerate(audio_file_ids):
        track_data = schemas.CollectionTrackCreate(
            audio_file_id=audio_file_id,
            track_order=start_order + i
        )
        track = add_track_to_collection(db, collection_id, track_data, added_by_id)
        if track:
            added_tracks.append(track)
    
    return added_tracks

# ============= COLLECTION COLLABORATION CRUD =============

def add_collection_collaborator(
    db: Session, 
    collection_id: int, 
    collaborator_data: schemas.CollectionCollaboratorCreate,
    added_by_id: int
) -> Optional[models.CollectionCollaborator]:
    #check if already a collaborator
    existing = db.query(models.CollectionCollaborator).filter(
        and_(models.CollectionCollaborator.collection_id == collection_id,
             models.CollectionCollaborator.user_id == collaborator_data.user_id)
    ).first()
    if existing:
        return None
    
    db_collaborator = models.CollectionCollaborator(
        collection_id=collection_id,
        user_id=collaborator_data.user_id,
        permission_level=collaborator_data.permission_level,
        added_by_id=added_by_id
    )
    db.add(db_collaborator)
    db.commit()
    db.refresh(db_collaborator)
    return db_collaborator

def update_collection_collaborator(
    db: Session, 
    collection_id: int, 
    user_id: int, 
    update_data: schemas.CollectionCollaboratorUpdate
) -> Optional[models.CollectionCollaborator]:
    db_collaborator = db.query(models.CollectionCollaborator).filter(
        and_(models.CollectionCollaborator.collection_id == collection_id,
             models.CollectionCollaborator.user_id == user_id)
    ).first()
    if db_collaborator:
        db_collaborator.permission_level = update_data.permission_level
        db.commit()
        db.refresh(db_collaborator)
    return db_collaborator

def remove_collection_collaborator(db: Session, collection_id: int, user_id: int) -> bool:
    db_collaborator = db.query(models.CollectionCollaborator).filter(
        and_(models.CollectionCollaborator.collection_id == collection_id,
             models.CollectionCollaborator.user_id == user_id)
    ).first()
    if db_collaborator:
        db.delete(db_collaborator)
        db.commit()
        return True
    return False

def user_can_edit_collection(db: Session, collection_id: int, user_id: int) -> Tuple[bool, str]:
    collection = db.query(models.Collection).filter(models.Collection.id == collection_id).first()
    if not collection:
        return False, "Collection not found"
    
    #wwner can always edit
    if collection.owner_id == user_id:
        return True, "owner"
    
    #check if collection allows collaboration
    if not collection.is_collaborative:
        return False, "Not collaborative"
    
    #check collaborator permissions
    collaborator = db.query(models.CollectionCollaborator).filter(
        and_(models.CollectionCollaborator.collection_id == collection_id,
             models.CollectionCollaborator.user_id == user_id)
    ).first()
    
    if collaborator and collaborator.permission_level == "edit":
        return True, "collaborator"
    
    return False, "No permission"

def user_can_view_collection(db: Session, collection_id: int, user_id: int) -> Tuple[bool, str]:
    collection = db.query(models.Collection).filter(models.Collection.id == collection_id).first()
    if not collection:
        return False, "Collection not found"
    
    #owner can always view
    if collection.owner_id == user_id:
        return True, "owner"
    
    #public collections can be viewed by anyone
    if collection.is_public:
        return True, "public"
    
    #check if user is a collaborator
    collaborator = db.query(models.CollectionCollaborator).filter(
        and_(models.CollectionCollaborator.collection_id == collection_id,
             models.CollectionCollaborator.user_id == user_id)
    ).first()
    
    if collaborator:
        return True, "collaborator"
    
    return False, "No access"

# ============= COLLECTION STATS =============

def get_collection_stats(db: Session, user_id: Optional[int] = None) -> dict:
    if user_id:
        query_filter = models.Collection.owner_id == user_id
        total_collections = db.query(models.Collection).filter(query_filter).count()
        total_albums = db.query(models.Collection).filter(
            and_(query_filter, models.Collection.collection_type == schemas.CollectionType.ALBUM)
        ).count()
        total_playlists = db.query(models.Collection).filter(
            and_(query_filter, models.Collection.collection_type == schemas.CollectionType.PLAYLIST)
        ).count()
        total_compilations = db.query(models.Collection).filter(
            and_(query_filter, models.Collection.collection_type == schemas.CollectionType.COMPILATION)
        ).count()
        public_collections = db.query(models.Collection).filter(
            and_(query_filter, models.Collection.is_public == True)
        ).count()
        collaborative_collections = db.query(models.Collection).filter(
            and_(query_filter, models.Collection.is_collaborative == True)
        ).count()
    else:
        total_collections = db.query(models.Collection).count()
        total_albums = db.query(models.Collection).filter(
            models.Collection.collection_type == schemas.CollectionType.ALBUM
        ).count()
        total_playlists = db.query(models.Collection).filter(
            models.Collection.collection_type == schemas.CollectionType.PLAYLIST
        ).count()
        total_compilations = db.query(models.Collection).filter(
            models.Collection.collection_type == schemas.CollectionType.COMPILATION
        ).count()
        public_collections = db.query(models.Collection).filter(models.Collection.is_public == True).count()
        collaborative_collections = db.query(models.Collection).filter(models.Collection.is_collaborative == True).count()
    
    return {
        "total_collections": total_collections,
        "total_albums": total_albums,
        "total_playlists": total_playlists,
        "total_compilations": total_compilations,
        "public_collections": public_collections,
        "collaborative_collections": collaborative_collections
    }

def get_recent_collections(db: Session, limit: int = 20, collection_type: Optional[schemas.CollectionType] = None) -> List[models.Collection]:
    query = db.query(models.Collection).options(joinedload(models.Collection.owner))
    
    if collection_type:
        query = query.filter(models.Collection.collection_type == collection_type)
    
    return query.order_by(models.Collection.created_date.desc()).limit(limit).all()

# ============= CONVENIENCE FUNCTIONS =============

def get_albums(db: Session, **kwargs) -> List[models.Collection]:
    return get_collections(db, collection_type=schemas.CollectionType.ALBUM, **kwargs)

def get_playlists(db: Session, **kwargs) -> List[models.Collection]:
    return get_collections(db, collection_type=schemas.CollectionType.PLAYLIST, **kwargs)

def get_compilations(db: Session, **kwargs) -> List[models.Collection]:
    return get_collections(db, collection_type=schemas.CollectionType.COMPILATION, **kwargs)

def create_album(db: Session, album: schemas.AlbumCreate, owner_id: int) -> models.Collection:
    return create_collection(db, album, owner_id)

def create_playlist(db: Session, playlist: schemas.PlaylistCreate, owner_id: int) -> models.Collection:
    return create_collection(db, playlist, owner_id)

def create_compilation(db: Session, compilation: schemas.CompilationCreate, owner_id: int) -> models.Collection:
    return create_collection(db, compilation, owner_id)

# ============= TOKEN BLACKLIST CRUD =============

def add_revoked_token(db: Session, jti: str, token: str, token_type: str, user_id: int, expires_at, reason: str = None):
    #check if token is already revoked
    existing = db.query(models.RevokedToken).filter(models.RevokedToken.jti == jti).first()
    if existing:
        #token already revoked, just return the existing record
        return existing

    #add new revoked token
    revoked_token = models.RevokedToken(
        jti=jti,
        token=token,
        token_type=token_type,
        user_id=user_id,
        expires_at=expires_at,
        reason=reason
    )
    db.add(revoked_token)
    db.commit()
    return revoked_token

def is_token_revoked(db: Session, jti: str) -> bool:
    return db.query(models.RevokedToken).filter(models.RevokedToken.jti == jti).first() is not None

def cleanup_expired_tokens(db: Session):
    from datetime import datetime
    deleted = db.query(models.RevokedToken).filter(
        models.RevokedToken.expires_at < datetime.utcnow()
    ).delete()
    db.commit()
    return deleted

def revoke_all_user_tokens(db: Session, user_id: int, reason: str = "password_change"):
    pass

# ============= AUDIT LOG CRUD =============

def create_audit_log(
    db: Session,
    action: str,
    user_id: int = None,
    resource_type: str = None,
    resource_id: str = None,
    ip_address: str = None,
    user_agent: str = None,
    details: str = None,
    success: bool = True
):
    audit_log = models.AuditLog(
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        success=success
    )
    db.add(audit_log)
    db.commit()
    return audit_log

def get_audit_logs(
    db: Session,
    user_id: int = None,
    action: str = None,
    skip: int = 0,
    limit: int = 100
):
    query = db.query(models.AuditLog)
    if user_id:
        query = query.filter(models.AuditLog.user_id == user_id)
    if action:
        query = query.filter(models.AuditLog.action == action)
    return query.order_by(models.AuditLog.timestamp.desc()).offset(skip).limit(limit).all()

def cleanup_old_audit_logs(db: Session, retention_days: int = 365):
    from datetime import datetime, timedelta
    cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
    deleted = db.query(models.AuditLog).filter(
        models.AuditLog.timestamp < cutoff_date
    ).delete()
    db.commit()
    return deleted

# ============= USER CONSENT CRUD =============

def create_user_consent(
    db: Session,
    user_id: int,
    consent_type: str,
    consent_version: str,
    ip_address: str = None
):
    consent = models.UserConsent(
        user_id=user_id,
        consent_type=consent_type,
        consent_version=consent_version,
        ip_address=ip_address
    )
    db.add(consent)
    db.commit()
    return consent

def get_user_consents(db: Session, user_id: int):
    return db.query(models.UserConsent).filter(
        models.UserConsent.user_id == user_id
    ).all()

def withdraw_consent(db: Session, consent_id: int):
    from datetime import datetime
    consent = db.query(models.UserConsent).filter(models.UserConsent.id == consent_id).first()
    if consent:
        consent.withdrawn_at = datetime.utcnow()
        consent.is_active = False
        db.commit()
    return consent

# ============= DATA RETENTION POLICY CRUD =============

def create_retention_policy(
    db: Session,
    data_type: str,
    retention_days: int,
    description: str = None
):
    policy = db.query(models.DataRetentionPolicy).filter(
        models.DataRetentionPolicy.data_type == data_type
    ).first()

    if policy:
        policy.retention_days = retention_days
        policy.description = description
        from datetime import datetime
        policy.updated_at = datetime.utcnow()
    else:
        policy = models.DataRetentionPolicy(
            data_type=data_type,
            retention_days=retention_days,
            description=description
        )
        db.add(policy)

    db.commit()
    return policy

def get_retention_policy(db: Session, data_type: str):
    return db.query(models.DataRetentionPolicy).filter(
        models.DataRetentionPolicy.data_type == data_type
    ).first()

def get_all_retention_policies(db: Session):
    return db.query(models.DataRetentionPolicy).all()

# ============= USER DELETION REQUEST CRUD =============

def create_deletion_request(
    db: Session,
    user_id: int,
    scheduled_deletion_at,
    deletion_type: str = "soft",
    reason: str = None
):
    deletion_request = models.UserDeletionRequest(
        user_id=user_id,
        scheduled_deletion_at=scheduled_deletion_at,
        deletion_type=deletion_type,
        reason=reason,
        status="pending"
    )
    db.add(deletion_request)
    db.commit()
    return deletion_request

def get_deletion_request(db: Session, user_id: int):
    return db.query(models.UserDeletionRequest).filter(
        and_(
            models.UserDeletionRequest.user_id == user_id,
            models.UserDeletionRequest.status == "pending"
        )
    ).first()

def cancel_deletion_request(db: Session, request_id: int):
    from datetime import datetime
    request = db.query(models.UserDeletionRequest).filter(
        models.UserDeletionRequest.id == request_id
    ).first()
    if request:
        request.status = "cancelled"
        request.cancelled_at = datetime.utcnow()
        db.commit()
    return request

def complete_deletion_request(db: Session, request_id: int):
    from datetime import datetime
    request = db.query(models.UserDeletionRequest).filter(
        models.UserDeletionRequest.id == request_id
    ).first()
    if request:
        request.status = "completed"
        request.completed_at = datetime.utcnow()
        db.commit()
    return request

def get_pending_deletions(db: Session):
    from datetime import datetime
    return db.query(models.UserDeletionRequest).filter(
        and_(
            models.UserDeletionRequest.status == "pending",
            models.UserDeletionRequest.scheduled_deletion_at <= datetime.utcnow()
        )
    ).all()

# ============= USER DELETION CRUD =============

def soft_delete_user(db: Session, user_id: int):
    from app.core.storage import minio_client

    user = get_user(db, user_id)
    if not user:
        return None

    #delete profile picture from MinIO
    if user.profile_picture_url:
        try:
            filename = user.profile_picture_url.split('/')[-1]
            minio_client.remove_object("profile-pictures", filename)
        except Exception as e:
            print(f"Error deleting profile picture: {e}")

    #anonymize user data
    user.is_active = False
    user.username = f"deleted_user_{user_id}"
    user.email = f"deleted_{user_id}@deleted.account"
    user.display_name = None
    user.bio = "deleted"
    user.profile_picture_url = None

    #make all users audio files private
    db.query(models.AudioFile).filter(
        models.AudioFile.owner_id == user_id
    ).update({"is_public": False})

    #make all users collections private
    db.query(models.Collection).filter(
        models.Collection.owner_id == user_id
    ).update({"is_public": False})

    db.commit()
    db.refresh(user)

    return user

def hard_delete_user(db: Session, user_id: int):
    from app.core.storage import minio_client

    user = get_user(db, user_id)
    if not user:
        return None

    #delete profile picture from MinIO
    if user.profile_picture_url:
        try:
            #extract filename from URL
            filename = user.profile_picture_url.split('/')[-1]
            minio_client.remove_object("profile-pictures", filename)
        except Exception as e:
            print(f"Error deleting profile picture: {e}")

    #delete all audio files
    audio_files = db.query(models.AudioFile).filter(models.AudioFile.owner_id == user_id).all()
    for audio_file in audio_files:
        try:
            minio_client.remove_object("audio-files", audio_file.stored_filename)
        except Exception as e:
            print(f"Error deleting audio file {audio_file.id}: {e}")

    #delete all collections and their cover art
    collections = db.query(models.Collection).filter(models.Collection.owner_id == user_id).all()
    for collection in collections:
        if collection.cover_art_url:
            try:
                filename = collection.cover_art_url.split('/')[-1]
                minio_client.remove_object("cover-art", filename)
            except Exception as e:
                print(f"Error deleting cover art: {e}")

    #database CASCADE will handle:
    # - audio_files
    # - collections
    # - collection_tracks (via collection cascade)
    # - collection_collaborators (via collection cascade)
    # - files
    # - revoked_tokens
    # - audit_logs
    # - user_consents

    db.query(models.AuditLog).filter(models.AuditLog.user_id == user_id).update(
        {"user_id": None, "details": "User deleted - GDPR"}
    )

    db.delete(user)
    db.commit()

    return True

# ============= ANNOUNCEMENT CRUD =============

def create_announcement(db: Session, announcement: schemas.AnnouncementCreate, created_by_id: int) -> models.Announcement:
    from datetime import datetime

    db_announcement = models.Announcement(
        title=announcement.title,
        content=announcement.content,
        is_published=announcement.is_published,
        published_date=datetime.utcnow() if announcement.is_published else None,
        created_by_id=created_by_id
    )
    db.add(db_announcement)
    db.commit()
    db.refresh(db_announcement)
    return db_announcement

def get_announcement(db: Session, announcement_id: int) -> Optional[models.Announcement]:
    return db.query(models.Announcement).options(
        joinedload(models.Announcement.created_by)
    ).filter(models.Announcement.id == announcement_id).first()

def get_announcements(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    published_only: bool = False
) -> List[models.Announcement]:
    query = db.query(models.Announcement).options(joinedload(models.Announcement.created_by))

    if published_only:
        query = query.filter(models.Announcement.is_published == True)

    return query.order_by(models.Announcement.created_date.desc()).offset(skip).limit(limit).all()

def get_announcements_count(db: Session, published_only: bool = False) -> int:
    query = db.query(models.Announcement)

    if published_only:
        query = query.filter(models.Announcement.is_published == True)

    return query.count()

def update_announcement(
    db: Session,
    announcement_id: int,
    announcement_update: schemas.AnnouncementUpdate
) -> Optional[models.Announcement]:
    from datetime import datetime

    db_announcement = db.query(models.Announcement).filter(
        models.Announcement.id == announcement_id
    ).first()

    if db_announcement:
        update_dict = announcement_update.dict(exclude_unset=True)

        #if publishing for the first time, set published_date
        if 'is_published' in update_dict and update_dict['is_published'] and not db_announcement.is_published:
            db_announcement.published_date = datetime.utcnow()
        #if unpublishing, clear published_date
        elif 'is_published' in update_dict and not update_dict['is_published']:
            db_announcement.published_date = None

        for key, value in update_dict.items():
            setattr(db_announcement, key, value)

        db.commit()
        db.refresh(db_announcement)

    return db_announcement

def delete_announcement(db: Session, announcement_id: int) -> bool:
    db_announcement = db.query(models.Announcement).filter(
        models.Announcement.id == announcement_id
    ).first()

    if db_announcement:
        db.delete(db_announcement)
        db.commit()
        return True

    return False

# ============= PASSWORD RESET TOKEN CRUD =============

def create_password_reset_token(db: Session, user_id: int, token: str, expires_at, ip_address: str = None):
    reset_token = models.PasswordResetToken(
        user_id=user_id,
        token=token,
        expires_at=expires_at,
        ip_address=ip_address
    )
    db.add(reset_token)
    db.commit()
    db.refresh(reset_token)
    return reset_token

def get_password_reset_token(db: Session, token: str):
    return db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token == token
    ).first()

def invalidate_password_reset_token(db: Session, token_id: int):
    from datetime import datetime
    token = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.id == token_id
    ).first()
    if token:
        token.is_valid = False
        token.used_at = datetime.utcnow()
        db.commit()
    return token

def invalidate_all_user_reset_tokens(db: Session, user_id: int):
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.user_id == user_id,
        models.PasswordResetToken.is_valid == True
    ).update({"is_valid": False})
    db.commit()

def cleanup_expired_reset_tokens(db: Session):
    from datetime import datetime
    deleted = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.expires_at < datetime.utcnow()
    ).delete()
    db.commit()
    return deleted