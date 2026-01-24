import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Header, Request
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from typing import List, Optional
from pydantic import ValidationError
import uuid
import logging
import io
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.storage import minio_client
from app.core.email import send_password_reset_email
from app.core.security import get_current_active_superuser


from .. import crud, models, schemas
from ..core.security import create_access_token, create_refresh_token
from ..core.crypto import CryptoHandler
from ..core.hashing import Hasher
from ..dependencies import get_db, get_current_user, get_current_active_user
from jose import jwt, JWTError

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(
    prefix="/users",
    tags=["users"]
)

crypto_handler = CryptoHandler()

@router.post("/", response_model=schemas.User)
@limiter.limit("5/minute")
def create_user(
    request: Request,
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    x_password_encrypted: Optional[str] = Header(None)
):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    existing_username = crud.get_user_by_username(db, username=user.username)
    if existing_username:
        raise HTTPException(status_code=400, detail="Username already taken")

    password = user.password
    if x_password_encrypted == "true":
        try:
            password = crypto_handler.decrypt_password(password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid encrypted password")
    
    try:
        user_data = schemas.UserCreate(
            username=user.username,
            email=user.email,
            password=password,
            display_name=user.display_name
        )
    except ValidationError as e:
        error_msg = e.errors()[0].get("msg", "Invalid input") if e.errors() else "Invalid input"
        raise HTTPException(status_code=422, detail=error_msg)

    return crud.create_user(db=db, user=user_data)

@router.get("/", response_model=List[schemas.UserPublic])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_current_active_superuser)
):
    users = crud.get_users(skip=skip, limit=limit)
    return users

@router.get("/search", response_model=List[schemas.UserPublic])
async def search_users(
    query: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_active_user),
    skip: int = 0,
    limit: int = 10
):
    if not query or len(query.strip()) < 2:
        raise HTTPException(
            status_code=400, 
            detail="Query must be at least 2 characters"
        )
    
    users = db.query(models.User).filter(
        models.User.username.ilike(f"%{query.strip()}%"),
        models.User.is_active == True
    ).offset(skip).limit(limit).all()
    
    return users

@router.get("/public-key")
async def get_public_key():
    try:
        key_path = settings.BASE_DIR / "core" / "keys" / "public_key.pem"
        if not key_path.exists():
            raise HTTPException(status_code=500, detail="Public key not found")
        return {"public_key": key_path.read_text()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not read public key: {str(e)}")

@router.get("/me", response_model=schemas.UserDetail)
async def read_user_me(
    current_user: models.User = Depends(get_current_active_user)
):
    return current_user

@router.post("/token", response_model=schemas.Token)
@limiter.limit("10/minute")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    x_password_encrypted: Optional[str] = Header(None)
):
    password = form_data.password
    if x_password_encrypted == "true":
        try:
            password = crypto_handler.decrypt_password(password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid encrypted password")

    user = crud.get_user_by_email(db, email=form_data.username)
    if not user:
        user = crud.get_user_by_username(db, username=form_data.username)

    if not user or not Hasher.verify_password(password, user.hashed_password):
        crud.create_audit_log(
            db=db,
            action="login.failed",
            details=f"Failed login attempt for: {form_data.username}",
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        crud.create_audit_log(
            db=db,
            action="login.failed.inactive",
            user_id=user.id,
            details=f"Login attempt for deactivated account: {user.username}",
            success=False
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Please contact support to reactivate your account.",
        )

    access_token, access_jti, access_expires = create_access_token(data={"sub": user.username})
    refresh_token, refresh_jti, refresh_expires = create_refresh_token(data={"sub": user.username})

    crud.create_audit_log(
        db=db,
        action="login.success",
        user_id=user.id,
        details=f"User logged in: {user.username}",
        success=True
    )

    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}

@router.post("/token/refresh", response_model=schemas.Token)
@limiter.limit("30/minute")
def refresh_token(request: Request, token_request_body: schemas.RefreshTokenRequest, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token_request_body.refresh_token, settings.REFRESH_TOKEN_SECRET_KEY, algorithms=[settings.REFRESH_TOKEN_ALGORITHM])

        old_jti = payload.get("jti")
        if old_jti and crud.is_token_revoked(db, old_jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception

        token_type = payload.get("token_type")
        if token_type != "refresh":
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception

    if old_jti:
        old_expires = payload.get("exp")
        if old_expires:
            from datetime import datetime
            crud.add_revoked_token(
                db=db,
                jti=old_jti,
                token=token_request_body.refresh_token,
                token_type="refresh",
                user_id=user.id,
                expires_at=datetime.fromtimestamp(old_expires),
                reason="token_refresh"
            )

    new_access_token, access_jti, access_expires = create_access_token(data={"sub": user.username})
    new_refresh_token, refresh_jti, refresh_expires = create_refresh_token(data={"sub": user.username})

    crud.create_audit_log(
        db=db,
        action="token.refresh",
        user_id=user.id,
        details=f"Token refreshed for user: {user.username}",
        success=True
    )

    return {"access_token": new_access_token, "token_type": "bearer", "refresh_token": new_refresh_token}

@router.put("/me", response_model=schemas.User)
def update_user_me(
    user_update: schemas.UserUpdate, 
    current_user: models.User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if user_update.display_name is not None:
        display_name = user_update.display_name.strip()
        if len(display_name) > 50:
            raise HTTPException(status_code=400, detail="Display name cannot exceed 50 characters")
        if len(display_name) < 1:
            raise HTTPException(status_code=400, detail="Display name cannot be empty")
        current_user.display_name = display_name

    if user_update.bio is not None:
        if len(user_update.bio) > 280:
            raise HTTPException(status_code=400, detail="Bio cannot exceed 280 characters")
        current_user.bio = user_update.bio
    
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/me/upload-profile-picture", response_model=schemas.User)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allowed_types = ["image/png", "image/jpeg", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, or WebP images are allowed")

    file_size = 0
    contents = await file.read()
    file_size = len(contents)
    
    if file_size > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    
    file_extension = file.filename.split(".")[-1] if "." in file.filename else "png"
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    try:
        minio_client.put_object(
            bucket_name=settings.MINIO_BUCKET_NAME,
            object_name=unique_filename,
            data=io.BytesIO(contents),
            length=len(contents),
            content_type=file.content_type
        )

        file_url = f"http://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET_NAME}/{unique_filename}"

        current_user.profile_picture_url = file_url
        db.commit()
        db.refresh(current_user)

        return current_user

    except Exception as e:
        logging.error(f"Error uploading profile picture to Minio: {e}")
        raise HTTPException(status_code=500, detail="Could not upload file.")

    return current_user

# ============= SECURITY & SESSION MANAGEMENT =============

@router.post("/logout")
def logout(
    token_request_body: schemas.RefreshTokenRequest,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        payload = jwt.decode(
            token_request_body.refresh_token,
            settings.REFRESH_TOKEN_SECRET_KEY,
            algorithms=[settings.REFRESH_TOKEN_ALGORITHM]
        )

        jti = payload.get("jti")
        expires = payload.get("exp")

        if jti and expires:
            from datetime import datetime
            crud.add_revoked_token(
                db=db,
                jti=jti,
                token=token_request_body.refresh_token,
                token_type="refresh",
                user_id=current_user.id,
                expires_at=datetime.fromtimestamp(expires),
                reason="logout"
            )

        # Log logout
        crud.create_audit_log(
            db=db,
            action="logout.success",
            user_id=current_user.id,
            details=f"User logged out: {current_user.username}",
            success=True
        )

        return {"message": "Successfully logged out"}

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

# ============= ACCOUNT DELETION (GDPR) =============

@router.post("/me/request-deletion")
def request_account_deletion(
    deletion_request: schemas.DeletionRequest,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from datetime import datetime, timedelta

    existing_request = crud.get_deletion_request(db, current_user.id)
    if existing_request:
        raise HTTPException(
            status_code=400,
            detail=f"Deletion already requested. Scheduled for {existing_request.scheduled_deletion_at.isoformat()}. Use /users/me/cancel-deletion to undo."
        )

    scheduled_deletion = datetime.utcnow() + timedelta(days=7)

    deletion_req = crud.create_deletion_request(
        db=db,
        user_id=current_user.id,
        scheduled_deletion_at=scheduled_deletion,
        deletion_type=deletion_request.deletion_type,
        reason=deletion_request.reason
    )

    crud.create_audit_log(
        db=db,
        action="user.deletion_requested",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
        details=f"User requested {deletion_request.deletion_type} deletion. Scheduled for {scheduled_deletion.isoformat()}. Reason: {deletion_request.reason}",
        success=True
    )

    return {
        "message": "Account deletion scheduled. Your account will remain active for 7 days. Cancel anytime using /users/me/cancel-deletion",
        "scheduled_deletion_at": scheduled_deletion.isoformat(),
        "grace_period_days": 7,
        "deletion_type": deletion_request.deletion_type,
        "can_cancel_until": scheduled_deletion.isoformat()
    }

@router.post("/me/cancel-deletion")
def cancel_account_deletion(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    deletion_request = crud.get_deletion_request(db, current_user.id)
    if not deletion_request:
        raise HTTPException(status_code=404, detail="No pending deletion request found")

    crud.cancel_deletion_request(db, deletion_request.id)

    crud.create_audit_log(
        db=db,
        action="user.deletion_cancelled",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
        details="User cancelled account deletion request",
        success=True
    )

    return {"message": "Account deletion cancelled"}

@router.get("/me/deletion-status")
def get_deletion_status(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    deletion_request = crud.get_deletion_request(db, current_user.id)

    if deletion_request:
        from datetime import datetime
        time_remaining = (deletion_request.scheduled_deletion_at - datetime.utcnow()).total_seconds()
        days_remaining = time_remaining / 86400

        return {
            "has_pending_deletion": True,
            "deletion_type": deletion_request.deletion_type,
            "scheduled_deletion_at": deletion_request.scheduled_deletion_at.isoformat(),
            "days_remaining": round(days_remaining, 2),
            "can_cancel": True,
            "reason": deletion_request.reason
        }
    else:
        return {
            "has_pending_deletion": False
        }

@router.delete("/me")
@limiter.limit("3/hour")
def delete_account_immediately(
    request: Request,
    password: str,
    deletion_type: str = "soft",
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.core.hashing import Hasher

    if not Hasher.verify_password(password, current_user.hashed_password):
        crud.create_audit_log(
            db=db,
            action="user.deletion_failed",
            user_id=current_user.id,
            details="Failed account deletion attempt - incorrect password",
            success=False
        )
        raise HTTPException(status_code=401, detail="Incorrect password")

    crud.create_audit_log(
        db=db,
        action=f"user.{deletion_type}_delete",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
        details=f"User account {deletion_type} deleted",
        success=True
    )

    if deletion_type == "soft":
        crud.soft_delete_user(db, current_user.id)
        return {"message": "Account deactivated (soft delete)"}
    elif deletion_type == "hard":
        crud.hard_delete_user(db, current_user.id)
        return {"message": "Account permanently deleted (hard delete - GDPR)"}
    else:
        raise HTTPException(status_code=400, detail="Invalid deletion_type. Must be 'soft' or 'hard'")

# ============= GDPR DATA EXPORT =============

@router.get("/me/export-data")
def export_user_data(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):

    audio_files = db.query(models.AudioFile).filter(models.AudioFile.owner_id == current_user.id).all()
    collections = db.query(models.Collection).filter(models.Collection.owner_id == current_user.id).all()
    consents = crud.get_user_consents(db, current_user.id)
    audit_logs = crud.get_audit_logs(db, user_id=current_user.id, limit=1000)

    user_data = {
        "user_profile": {
            "id": current_user.id,
            "username": current_user.username,
            "email": current_user.email,
            "display_name": current_user.display_name,
            "bio": current_user.bio,
            "profile_picture_url": current_user.profile_picture_url,
            "is_active": current_user.is_active,
            "is_superuser": current_user.is_superuser,
            "max_audio_uploads": current_user.max_audio_uploads
        },
        "audio_files": [
            {
                "id": af.id,
                "original_filename": af.original_filename,
                "title": af.title,
                "description": af.description,
                "file_size": af.file_size,
                "duration": af.duration,
                "upload_date": af.upload_date.isoformat() if af.upload_date else None,
                "is_public": af.is_public
            } for af in audio_files
        ],
        "collections": [
            {
                "id": col.id,
                "title": col.title,
                "description": col.description,
                "collection_type": col.collection_type,
                "artist": col.artist,
                "is_public": col.is_public,
                "created_date": col.created_date.isoformat() if col.created_date else None
            } for col in collections
        ],
        "consents": [
            {
                "consent_type": consent.consent_type,
                "consent_version": consent.consent_version,
                "given_at": consent.given_at.isoformat() if consent.given_at else None,
                "is_active": consent.is_active
            } for consent in consents
        ],
        "audit_logs": [
            {
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "success": log.success
            } for log in audit_logs
        ]
    }

    crud.create_audit_log(
        db=db,
        action="user.data_exported",
        user_id=current_user.id,
        resource_type="user",
        resource_id=str(current_user.id),
        details="User exported personal data (GDPR SAR)",
        success=True
    )

    return user_data

# ============= CONSENT MANAGEMENT =============

@router.post("/me/consent")
def record_consent(
    consent: schemas.ConsentCreate,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    consent_record = crud.create_user_consent(
        db=db,
        user_id=current_user.id,
        consent_type=consent.consent_type,
        consent_version=consent.consent_version,
        ip_address=consent.ip_address
    )

    crud.create_audit_log(
        db=db,
        action="consent.given",
        user_id=current_user.id,
        details=f"Consent given: {consent.consent_type} v{consent.consent_version}",
        success=True
    )

    return {"message": "Consent recorded", "consent_id": consent_record.id}

@router.get("/me/consents")
def get_user_consents_endpoint(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    consents = crud.get_user_consents(db, current_user.id)
    return consents

# ============= PASSWORD RESET =============

@router.post("/forgot-password", response_model=schemas.PasswordResetResponse)
@limiter.limit("3/hour")
def forgot_password(
    request: Request,
    reset_request: schemas.PasswordResetRequest,
    db: Session = Depends(get_db)
):
    user = crud.get_user_by_email(db, reset_request.email)
    
    if user:
        reset_token = secrets.token_urlsafe(32)
        
        expires_at = datetime.utcnow() + timedelta(hours=1)

        ip_address = request.client.host if request.client else None

        crud.create_password_reset_token(
            db=db,
            user_id=user.id,
            token=reset_token,
            expires_at=expires_at,
            ip_address=ip_address
        )

        email_sent = send_password_reset_email(
            email=user.email,
            reset_token=reset_token,
            username=user.username
        )
        
        crud.create_audit_log(
            db=db,
            action="password_reset.requested",
            user_id=user.id,
            ip_address=ip_address,
            details=f"Password reset requested for {user.email}",
            success=email_sent
        )
        
        if not email_sent:
            raise HTTPException(
                status_code=500,
                detail="Failed to send password reset email. Please try again later."
            )
    
    return schemas.PasswordResetResponse(
        message="If an account with that email exists, we've sent password reset instructions.",
        success=True
    )

@router.post("/verify-reset-token", response_model=schemas.PasswordResetResponse)
def verify_reset_token(
    verify_request: schemas.PasswordResetVerify,
    db: Session = Depends(get_db)
):
    
    reset_token = crud.get_password_reset_token(db, verify_request.token)
    
    if not reset_token:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token"
        )

    if not reset_token.is_valid:
        raise HTTPException(
            status_code=400,
            detail="This reset link has already been used"
        )
    
    if reset_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="This reset link has expired. Please request a new one."
        )
    
    return schemas.PasswordResetResponse(
        message="Reset token is valid",
        success=True
    )

@router.post("/reset-password", response_model=schemas.PasswordResetResponse)
@limiter.limit("5/hour")
def reset_password(
    request: Request,
    reset_confirm: schemas.PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    
    reset_token = crud.get_password_reset_token(db, reset_confirm.token)
    
    if not reset_token:
        crud.create_audit_log(
            db=db,
            action="password_reset.failed",
            details="Invalid reset token used",
            success=False
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token"
        )

    if not reset_token.is_valid:
        crud.create_audit_log(
            db=db,
            action="password_reset.failed",
            user_id=reset_token.user_id,
            details="Attempted to use already-used reset token",
            success=False
        )
        raise HTTPException(
            status_code=400,
            detail="This reset link has already been used"
        )

    if reset_token.expires_at < datetime.utcnow():
        crud.create_audit_log(
            db=db,
            action="password_reset.failed",
            user_id=reset_token.user_id,
            details="Attempted to use expired reset token",
            success=False
        )
        raise HTTPException(
            status_code=400,
            detail="This reset link has expired. Please request a new one."
        )

    user = crud.get_user(db, reset_token.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.hashed_password = Hasher.get_password_hash(reset_confirm.new_password)

    crud.invalidate_all_user_reset_tokens(db, user.id)
    
    db.commit()

    crud.create_audit_log(
        db=db,
        action="password_reset.success",
        user_id=user.id,
        ip_address=request.client.host if request.client else None,
        details=f"Password successfully reset for {user.email}",
        success=True
    )
    
    return schemas.PasswordResetResponse(
        message="Password has been reset successfully. You can now log in with your new password.",
        success=True
    )