import io
import uuid
import logging
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.config import settings
from app.core.storage import minio_client
from app.core.security import get_current_active_superuser

from .. import crud, models, schemas
from ..dependencies import get_db, get_optional_current_user, get_current_active_user

router = APIRouter(
    prefix="/collections",
    tags=["collections"]
)

MAX_COVER_ART_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp", "image/jpg"]

# ============= COLLECTION MANAGEMENT =============

@router.get("/", response_model=schemas.CollectionListResponse)
def get_collections(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    collection_type: Optional[schemas.CollectionType] = Query(None),
    public_only: bool = Query(False),
    collaborative_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    collections = crud.get_collections(
        db, 
        skip=skip, 
        limit=limit,
        collection_type=collection_type,
        public_only=public_only,
        collaborative_only=collaborative_only
    )
    
    collection_responses = []
    for collection in collections:
        collection_response = schemas.CollectionResponse(
            id=collection.id,
            title=collection.title,
            description=collection.description,
            collection_type=collection.collection_type,
            artist=collection.artist,
            curator_note=collection.curator_note,
            cover_art_url=collection.cover_art_url,
            is_public=collection.is_public,
            is_collaborative=collection.is_collaborative,
            created_date=collection.created_date,
            updated_date=collection.updated_date,
            owner_id=collection.owner_id,
            tracks=collection.tracks or [],
            collaborators=collection.collaborators or [],
            track_count=len(collection.tracks or []),
            can_edit=False
        )
        
        if hasattr(collection, 'owner') and collection.owner:
            collection_response.owner = collection.owner
            
        collection_responses.append(collection_response)
    
    total = crud.get_collections_count(db, collection_type=collection_type, public_only=public_only)
    has_more = (skip + limit) < total
    
    return {
        "collections": collection_responses,
        "total": total,
        "has_more": has_more,
        "collection_type": collection_type
    }

@router.get("/my-collections", response_model=schemas.CollectionListResponse)
def get_my_collections(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    collection_type: Optional[schemas.CollectionType] = Query(None),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collections = crud.get_collections(
        db, 
        skip=skip, 
        limit=limit,
        owner_id=current_user.id,
        collection_type=collection_type
    )
    
    collection_responses = []
    for collection in collections:
        collection_response = schemas.CollectionResponse(
            id=collection.id,
            title=collection.title,
            description=collection.description,
            collection_type=collection.collection_type,
            artist=collection.artist,
            curator_note=collection.curator_note,
            cover_art_url=collection.cover_art_url,
            is_public=collection.is_public,
            is_collaborative=collection.is_collaborative,
            created_date=collection.created_date,
            updated_date=collection.updated_date,
            owner_id=collection.owner_id,
            tracks=collection.tracks or [],
            collaborators=collection.collaborators or [],
            track_count=len(collection.tracks or []),
            can_edit=True
        )

        if hasattr(collection, 'owner') and collection.owner:
            collection_response.owner = collection.owner
            
        collection_responses.append(collection_response)
    
    total = crud.get_collections_count(db, owner_id=current_user.id, collection_type=collection_type)
    has_more = (skip + limit) < total
    
    return {
        "collections": collection_responses,
        "total": total,
        "has_more": has_more,
        "collection_type": collection_type
    }

@router.get("/collaborative", response_model=schemas.CollectionListResponse)
def get_collaborative_collections(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collaborator_collection_ids = db.query(models.CollectionCollaborator.collection_id).filter(
        models.CollectionCollaborator.user_id == current_user.id
    ).subquery()
    
    collections = db.query(models.Collection).filter(
        models.Collection.id.in_(collaborator_collection_ids)
    ).offset(skip).limit(limit).all()
    
    collection_responses = []
    for collection in collections:
        can_edit, reason = crud.user_can_edit_collection(db, collection.id, current_user.id)
        
        collection_response = schemas.CollectionResponse(
            id=collection.id,
            title=collection.title,
            description=collection.description,
            collection_type=collection.collection_type,
            artist=collection.artist,
            curator_note=collection.curator_note,
            cover_art_url=collection.cover_art_url,
            is_public=collection.is_public,
            is_collaborative=collection.is_collaborative,
            created_date=collection.created_date,
            updated_date=collection.updated_date,
            owner_id=collection.owner_id,
            tracks=collection.tracks or [],
            collaborators=collection.collaborators or [],
            track_count=len(collection.tracks or []),
            can_edit=can_edit
        )
        
        if hasattr(collection, 'owner') and collection.owner:
            collection_response.owner = collection.owner
            
        collection_responses.append(collection_response)
    
    total = len(collections)
    has_more = len(collections) == limit
    
    return {
        "collections": collection_responses,
        "total": total,
        "has_more": has_more
    }

@router.get("/stats", response_model=schemas.UserCollectionStats)
def get_my_collection_stats(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    stats = crud.get_collection_stats(db, user_id=current_user.id)
    return schemas.UserCollectionStats(
        user_id=current_user.id,
        username=current_user.username,
        **stats
    )

@router.post("/", response_model=schemas.Collection)
def create_collection(
    collection: schemas.CollectionCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return crud.create_collection(db, collection, current_user.id)

@router.get("/{collection_id}", response_model=schemas.CollectionResponse)
def get_collection(
    collection_id: int,
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    if collection.is_public:
        can_edit = False
        if current_user:
            can_edit, _ = crud.user_can_edit_collection(db, collection_id, current_user.id)
        
        response = schemas.CollectionResponse(
            id=collection.id,
            title=collection.title,
            description=collection.description,
            collection_type=collection.collection_type,
            artist=collection.artist,
            curator_note=collection.curator_note,
            cover_art_url=collection.cover_art_url,
            is_public=collection.is_public,
            is_collaborative=collection.is_collaborative,
            created_date=collection.created_date,
            updated_date=collection.updated_date,
            owner_id=collection.owner_id,
            tracks=collection.tracks or [],
            collaborators=collection.collaborators or [],
            track_count=len(collection.tracks or []),
            can_edit=can_edit
        )
        
        if hasattr(collection, 'owner') and collection.owner:
            response.owner = collection.owner
            
        return response

    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    can_view, _ = crud.user_can_view_collection(db, collection_id, current_user.id)
    if current_user.is_superuser:
        can_view = True
    if not can_view:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    can_edit, _ = crud.user_can_edit_collection(db, collection_id, current_user.id)

    response = schemas.CollectionResponse(
        id=collection.id,
        title=collection.title,
        description=collection.description,
        collection_type=collection.collection_type,
        artist=collection.artist,
        curator_note=collection.curator_note,
        cover_art_url=collection.cover_art_url,
        is_public=collection.is_public,
        is_collaborative=collection.is_collaborative,
        created_date=collection.created_date,
        updated_date=collection.updated_date,
        owner_id=collection.owner_id,
        tracks=collection.tracks or [],
        collaborators=collection.collaborators or [],
        track_count=len(collection.tracks or []),
        can_edit=can_edit
    )
    
    if hasattr(collection, 'owner') and collection.owner:
        response.owner = collection.owner
        
    return response

@router.put("/{collection_id}", response_model=schemas.Collection)
def update_collection(
    collection_id: int,
    collection_update: schemas.CollectionUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    can_edit, reason = crud.user_can_edit_collection(db, collection_id, current_user.id)
    if not can_edit and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this collection")
    
    updated_collection = crud.update_collection(db, collection_id, collection_update)
    return updated_collection

@router.delete("/{collection_id}")
def delete_collection(
    collection_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    if collection.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You can only delete your own collections")
    
    if collection.cover_art_url:
        try:
            filename = collection.cover_art_url.split("/")[-1]
            minio_client.remove_object("cover-art", filename)
        except Exception as e:
            logging.warning(f"Failed to delete cover art from MinIO: {e}")
    
    success = crud.delete_collection(db, collection_id)
    if success:
        return {"message": f"{collection.collection_type.title()} deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete collection")

# ============= COVER ART MANAGEMENT =============

@router.post("/{collection_id}/cover-art", response_model=schemas.Collection)
async def upload_collection_cover_art(
    collection_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    can_edit, reason = crud.user_can_edit_collection(db, collection_id, current_user.id)
    if not can_edit and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this collection")

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, or WebP images are allowed")

    contents = await file.read()
    file_size = len(contents)
    
    if file_size > MAX_COVER_ART_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    
    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty")

    file_extension = Path(file.filename).suffix if file.filename else ".jpg"
    stored_filename = f"{collection.collection_type}_{collection_id}_{uuid.uuid4()}{file_extension}"
    
    try:
        if collection.cover_art_url:
            old_filename = collection.cover_art_url.split("/")[-1]
            try:
                minio_client.remove_object("cover-art", old_filename)
            except:
                pass

        minio_client.put_object(
            bucket_name="cover-art",
            object_name=stored_filename,
            data=io.BytesIO(contents),
            length=file_size,
            content_type=file.content_type
        )

        file_url = f"http://{settings.MINIO_ENDPOINT}/cover-art/{stored_filename}"
        collection.cover_art_url = file_url
        db.commit()
        db.refresh(collection)
        
        return collection
        
    except Exception as e:
        logging.error(f"Error uploading cover art to MinIO: {e}")
        raise HTTPException(status_code=500, detail="Could not upload cover art")

# ============= TRACK MANAGEMENT =============

@router.post("/{collection_id}/tracks", response_model=schemas.CollectionTrack)
def add_track_to_collection(
    collection_id: int,
    track_data: schemas.CollectionTrackCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):

    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    can_edit, reason = crud.user_can_edit_collection(db, collection_id, current_user.id)
    if not can_edit and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this collection")

    audio_file = crud.get_audio_file(db, track_data.audio_file_id)
    if not audio_file:
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    if audio_file.owner_id != current_user.id and not audio_file.is_public:
        raise HTTPException(status_code=403, detail="You can only add your own or public audio files")
    
    track = crud.add_track_to_collection(db, collection_id, track_data, current_user.id)
    return track

@router.delete("/{collection_id}/tracks/{track_id}")
def remove_track_from_collection(
    collection_id: int,
    track_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    can_edit, reason = crud.user_can_edit_collection(db, collection_id, current_user.id)
    if not can_edit and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this collection")
    
    success = crud.remove_track_from_collection(db, collection_id, track_id)
    if success:
        return {"message": "Track removed from collection"}
    else:
        raise HTTPException(status_code=404, detail="Track not found in collection")

@router.put("/{collection_id}/tracks/{track_id}/reorder", response_model=schemas.CollectionTrack)
def reorder_collection_track(
    collection_id: int,
    track_id: int,
    reorder_data: schemas.CollectionTrackReorder,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    can_edit, reason = crud.user_can_edit_collection(db, collection_id, current_user.id)
    if not can_edit and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this collection")
    
    track = crud.reorder_collection_track(db, collection_id, track_id, reorder_data.new_order)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    
    return track

@router.post("/{collection_id}/tracks/bulk-add", response_model=List[schemas.CollectionTrack])
def bulk_add_tracks_to_collection(
    collection_id: int,
    bulk_data: schemas.BulkAddTracks,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    can_edit, reason = crud.user_can_edit_collection(db, collection_id, current_user.id)
    if not can_edit and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this collection")
    
    valid_audio_file_ids = []
    for audio_file_id in bulk_data.audio_file_ids:
        audio_file = crud.get_audio_file(db, audio_file_id)
        if audio_file and (audio_file.owner_id == current_user.id or audio_file.is_public):
            valid_audio_file_ids.append(audio_file_id)
    
    added_tracks = crud.bulk_add_tracks_to_collection(db, collection_id, valid_audio_file_ids, current_user.id)
    return added_tracks

@router.post("/{collection_id}/tracks/bulk-reorder")
def bulk_reorder_collection_tracks(
    collection_id: int,
    bulk_data: schemas.BulkReorderTracks,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Bulk reorder tracks in any collection"""
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    can_edit, reason = crud.user_can_edit_collection(db, collection_id, current_user.id)
    if not can_edit and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="You don't have permission to edit this collection")
    
    success_count = 0
    for reorder_item in bulk_data.track_orders:
        track = crud.reorder_collection_track(
            db, 
            collection_id, 
            reorder_item['track_id'], 
            reorder_item['new_order']
        )
        if track:
            success_count += 1
    
    return {
        "message": f"Successfully reordered {success_count} tracks",
        "processed": len(bulk_data.track_orders)
    }

# ============= COLLABORATION MANAGEMENT =============

@router.post("/{collection_id}/collaborators", response_model=schemas.CollectionCollaborator)
def add_collection_collaborator(
    collection_id: int,
    collaborator_data: schemas.CollectionCollaboratorCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    if collection.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only the collection owner can add collaborators")
    
    if not collection.is_collaborative:
        raise HTTPException(status_code=400, detail="Collection must be collaborative to add collaborators")
    
    collaborator_user = crud.get_user(db, collaborator_data.user_id)
    if not collaborator_user:
        raise HTTPException(status_code=404, detail="User not found")

    if collaborator_data.user_id == collection.owner_id:
        raise HTTPException(status_code=400, detail="Cannot add collection owner as collaborator")
    
    collaborator = crud.add_collection_collaborator(db, collection_id, collaborator_data, current_user.id)
    if not collaborator:
        raise HTTPException(status_code=400, detail="User is already a collaborator")
    
    return collaborator

@router.put("/{collection_id}/collaborators/{user_id}", response_model=schemas.CollectionCollaborator)
def update_collection_collaborator(
    collection_id: int,
    user_id: int,
    collaborator_update: schemas.CollectionCollaboratorUpdate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    if collection.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only the collection owner can update collaborator permissions")
    
    collaborator = crud.update_collection_collaborator(db, collection_id, user_id, collaborator_update)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    
    return collaborator

@router.delete("/{collection_id}/collaborators/{user_id}")
def remove_collection_collaborator(
    collection_id: int,
    user_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    if (collection.owner_id != current_user.id and 
        user_id != current_user.id and 
        not current_user.is_superuser):
        raise HTTPException(
            status_code=403, 
            detail="You can only remove yourself or (as owner) remove other collaborators"
        )
    
    success = crud.remove_collection_collaborator(db, collection_id, user_id)
    if success:
        return {"message": "Collaborator removed from collection"}
    else:
        raise HTTPException(status_code=404, detail="Collaborator not found")

# ============= TYPE-SPECIFIC CONVENIENCE ENDPOINTS =============

@router.get("/albums", response_model=schemas.CollectionListResponse)
def get_albums(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    public_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    return get_collections(skip=skip, limit=limit, collection_type=schemas.CollectionType.ALBUM, public_only=public_only, db=db)

@router.get("/playlists", response_model=schemas.CollectionListResponse)
def get_playlists(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    public_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    return get_collections(skip=skip, limit=limit, collection_type=schemas.CollectionType.PLAYLIST, public_only=public_only, db=db)

@router.get("/compilations", response_model=schemas.CollectionListResponse)
def get_compilations(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    public_only: bool = Query(False),
    db: Session = Depends(get_db)
):
    return get_collections(skip=skip, limit=limit, collection_type=schemas.CollectionType.COMPILATION, public_only=public_only, db=db)

# ============= ADMIN ENDPOINTS =============

@router.get("/admin/all", response_model=schemas.CollectionListResponse)
def admin_get_all_collections(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    collection_type: Optional[schemas.CollectionType] = Query(None),
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    collections = crud.get_collections(db, skip=skip, limit=limit, collection_type=collection_type)
    
    collection_responses = []
    for collection in collections:
        collection_response = schemas.CollectionResponse(
            id=collection.id,
            title=collection.title,
            description=collection.description,
            collection_type=collection.collection_type,
            artist=collection.artist,
            curator_note=collection.curator_note,
            cover_art_url=collection.cover_art_url,
            is_public=collection.is_public,
            is_collaborative=collection.is_collaborative,
            created_date=collection.created_date,
            updated_date=collection.updated_date,
            owner_id=collection.owner_id,
            tracks=collection.tracks or [],
            collaborators=collection.collaborators or [],
            track_count=len(collection.tracks or []),
            can_edit=True
        )

        if hasattr(collection, 'owner') and collection.owner:
            collection_response.owner = collection.owner
            
        collection_responses.append(collection_response)
    
    total = crud.get_collections_count(db, collection_type=collection_type)
    has_more = (skip + limit) < total
    
    return {
        "collections": collection_responses,
        "total": total,
        "has_more": has_more,
        "collection_type": collection_type
    }

@router.delete("/admin/{collection_id}")
def admin_delete_collection(
    collection_id: int,
    current_user: models.User = Depends(get_current_active_superuser),
    db: Session = Depends(get_db)
):
    collection = crud.get_collection(db, collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")
    
    collection_type = collection.collection_type

    if collection.cover_art_url:
        try:
            filename = collection.cover_art_url.split("/")[-1]
            minio_client.remove_object("cover-art", filename)
        except Exception as e:
            logging.warning(f"Failed to delete cover art: {e}")
    
    success = crud.delete_collection(db, collection_id)
    if success:
        return {"message": f"{collection_type.title()} {collection_id} deleted by admin"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete collection")