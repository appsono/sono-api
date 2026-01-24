from pydantic import BaseModel, EmailStr, field_validator, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ============= COLLECTION TYPE ENUM =============

class CollectionType(str, Enum):
    ALBUM = "album"
    PLAYLIST = "playlist"
    COMPILATION = "compilation"

# ============= USER SCHEMAS =============

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters with uppercase, lowercase, number, and special character")
    display_name: Optional[str] = Field(None, max_length=50)

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        import re
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/;~`]', v):
            raise ValueError('Password must contain at least one special character')
        return v

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                raise ValueError('Display name cannot be empty')
            if len(v) > 50:
                raise ValueError('Display name cannot exceed 50 characters')
            import re
            if not re.match(r'^[a-zA-Z0-9\s\-_.!@#$%&*()]+$', v):
                raise ValueError('Display name contains invalid characters')
        return v

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError('Username must be at least 3 characters')
        if len(v) > 50:
            raise ValueError('Username cannot exceed 50 characters')
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, hyphens, and underscores')
        return v

class UserUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=50)
    bio: Optional[str] = Field(None, max_length=280)

    @field_validator('display_name')
    @classmethod
    def validate_display_name(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                raise ValueError('Display name cannot be empty')
            if len(v) > 50:
                raise ValueError('Display name cannot exceed 50 characters')
        return v

    @field_validator('bio')
    @classmethod
    def validate_bio(cls, v):
        if v is not None and len(v) > 280:
            raise ValueError('Bio cannot exceed 280 characters')
        return v

class UserBase(BaseModel):
    username: str
    email: EmailStr
    display_name: Optional[str] = None
    bio: Optional[str] = None

class User(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    profile_picture_url: Optional[str] = None
    max_audio_uploads: int = 20
    total_audio_files: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class UserDetail(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    profile_picture_url: Optional[str] = None
    max_audio_uploads: int = 20
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class UserPublic(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    profile_picture_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ============= AUDIO FILE SCHEMAS =============

class AudioFileCreate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: bool = False

class AudioFileUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_public: Optional[bool] = None

class AudioFileBase(BaseModel):
    original_filename: str
    title: Optional[str] = None
    description: Optional[str] = None
    file_size: int
    duration: Optional[int] = None
    content_type: str
    is_public: bool = False

class AudioFile(AudioFileBase):
    id: int
    stored_filename: str
    file_url: str
    upload_date: datetime
    owner_id: int

    model_config = ConfigDict(from_attributes=True)

class AudioFileResponse(AudioFile):
    owner: Optional[UserPublic] = None

    model_config = ConfigDict(from_attributes=True)

class AudioFileListResponse(BaseModel):
    files: List[AudioFile]
    total: int
    has_more: bool

class AudioUploadStats(BaseModel):
    used_uploads: int
    max_uploads: int
    remaining_uploads: int

# ============= UNIFIED COLLECTION SCHEMAS =============

class CollectionCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    collection_type: CollectionType
    
    artist: Optional[str] = Field(None, max_length=100)  #for albums
    curator_note: Optional[str] = Field(None, max_length=1000)  #for compilations
    
    is_public: bool = False
    is_collaborative: bool = False

    @field_validator('is_collaborative')
    @classmethod
    def validate_collaboration(cls, v):
        return v

class CollectionUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    artist: Optional[str] = Field(None, max_length=100)
    curator_note: Optional[str] = Field(None, max_length=1000)
    is_public: Optional[bool] = None
    is_collaborative: Optional[bool] = None

class CollectionTrackCreate(BaseModel):
    audio_file_id: int
    track_order: Optional[int] = None

class CollectionTrackUpdate(BaseModel):
    track_order: int = Field(..., ge=1)

class CollectionTrack(BaseModel):
    id: int
    collection_id: int
    audio_file_id: int
    track_order: int
    added_date: datetime
    added_by_id: Optional[int] = None
    audio_file: Optional[AudioFile] = None
    added_by: Optional[UserPublic] = None

    model_config = ConfigDict(from_attributes=True)

class CollectionCollaboratorCreate(BaseModel):
    user_id: int
    permission_level: str = Field("edit", pattern="^(edit|view)$")

class CollectionCollaboratorUpdate(BaseModel):
    permission_level: str = Field(..., pattern="^(edit|view)$")

class CollectionCollaborator(BaseModel):
    id: int
    collection_id: int
    user_id: int
    permission_level: str
    added_date: datetime
    added_by_id: int
    user: Optional[UserPublic] = None
    added_by: Optional[UserPublic] = None

    model_config = ConfigDict(from_attributes=True)

class Collection(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    collection_type: CollectionType
    artist: Optional[str] = None
    curator_note: Optional[str] = None
    cover_art_url: Optional[str] = None
    is_public: bool
    is_collaborative: bool
    created_date: datetime
    updated_date: datetime
    owner_id: int
    owner: Optional[UserPublic] = None
    tracks: Optional[List[CollectionTrack]] = []
    collaborators: Optional[List[CollectionCollaborator]] = []

    model_config = ConfigDict(from_attributes=True)

class CollectionResponse(Collection):
    track_count: int = 0
    can_edit: bool = False

    @property
    def is_album(self) -> bool:
        return self.collection_type == CollectionType.ALBUM

    @property
    def is_playlist(self) -> bool:
        return self.collection_type == CollectionType.PLAYLIST

    @property
    def is_compilation(self) -> bool:
        return self.collection_type == CollectionType.COMPILATION

# ============= TYPE-SPECIFIC CONVENIENCE SCHEMAS =============

class AlbumCreate(CollectionCreate):
    collection_type: CollectionType = CollectionType.ALBUM
    artist: Optional[str] = Field(None, max_length=100, description="Album artist")

class PlaylistCreate(CollectionCreate):
    collection_type: CollectionType = CollectionType.PLAYLIST
    is_collaborative: bool = False

class CompilationCreate(CollectionCreate):
    collection_type: CollectionType = CollectionType.COMPILATION
    curator_note: Optional[str] = Field(None, max_length=1000, description="Curator's notes about this compilation")

Album = Collection
Playlist = Collection  
Compilation = Collection

AlbumResponse = CollectionResponse
PlaylistResponse = CollectionResponse
CompilationResponse = CollectionResponse

# ============= LIST RESPONSES =============

class CollectionListResponse(BaseModel):
    collections: List[CollectionResponse]
    total: int
    has_more: bool
    collection_type: Optional[CollectionType] = None 

AlbumListResponse = CollectionListResponse
PlaylistListResponse = CollectionListResponse
CompilationListResponse = CollectionListResponse

# ============= BULK OPERATIONS =============

class BulkAddTracks(BaseModel):
    audio_file_ids: List[int] = Field(..., min_length=1, max_length=50)

class BulkReorderTracks(BaseModel):
    track_orders: List[dict] = Field(..., description="List of {track_id: int, new_order: int}")

    @field_validator('track_orders')
    @classmethod
    def validate_track_orders(cls, v):
        for item in v:
            if not isinstance(item, dict) or 'track_id' not in item or 'new_order' not in item:
                raise ValueError('Each item must have track_id and new_order')
            if not isinstance(item['track_id'], int) or not isinstance(item['new_order'], int):
                raise ValueError('track_id and new_order must be integers')
            if item['new_order'] < 1:
                raise ValueError('new_order must be at least 1')
        return v

class CollectionTrackReorder(BaseModel):
    track_id: int
    new_order: int = Field(..., ge=1)

# ============= FILE SCHEMAS =============

class FileBase(BaseModel):
    filename: str
    content_type: str

class FileCreate(FileBase):
    pass

class File(FileBase):
    id: int
    upload_date: str
    file_url: str
    owner_id: int

    model_config = ConfigDict(from_attributes=True)

class FileResponse(File):
    owner: Optional[UserPublic] = None

    model_config = ConfigDict(from_attributes=True)

# ============= TOKEN SCHEMAS =============

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    token_type: Optional[str] = None

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# ============= COLLECTION STATS =============

class CollectionStats(BaseModel):
    total_collections: int
    total_albums: int
    total_playlists: int
    total_compilations: int
    public_collections: int
    collaborative_collections: int

class UserCollectionStats(CollectionStats):
    user_id: int
    username: str

    model_config = ConfigDict(from_attributes=True)

# ============= ADMIN SCHEMAS =============

class AdminStats(BaseModel):
    # User stats
    total_users: int
    active_users: int
    inactive_users: int
    superusers: Optional[int] = None
    total_audio_files: Optional[int] = None
    
    # Collection stats
    total_collections: Optional[int] = None
    total_albums: Optional[int] = None
    total_playlists: Optional[int] = None
    total_compilations: Optional[int] = None
    public_collections: Optional[int] = None
    collaborative_collections: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class UserUploadLimitUpdate(BaseModel):
    max_audio_uploads: int = Field(..., ge=0, le=1000, description="Maximum audio uploads allowed (0-1000)")

# ============= SECURITY & COMPLIANCE SCHEMAS =============

class DeletionRequest(BaseModel):
    deletion_type: str = Field("soft", pattern="^(soft|hard)$", description="Type of deletion: 'soft' or 'hard'")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for deletion")

class ConsentCreate(BaseModel):
    consent_type: str = Field(..., description="Type of consent (e.g., 'terms_of_service', 'privacy_policy')")
    consent_version: str = Field(..., description="Version of the consent document")
    ip_address: Optional[str] = None

class ConsentResponse(BaseModel):
    id: int
    user_id: int
    consent_type: str
    consent_version: str
    given_at: datetime
    withdrawn_at: Optional[datetime] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class RetentionPolicyCreate(BaseModel):
    data_type: str = Field(..., description="Type of data (e.g., 'audio_files', 'user_data', 'audit_logs')")
    retention_days: int = Field(..., ge=1, description="Number of days to retain the data")
    description: Optional[str] = None

class RetentionPolicyResponse(BaseModel):
    id: int
    data_type: str
    retention_days: int
    description: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ============= NEWS/ANNOUNCEMENTS SCHEMAS =============

class AnnouncementCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    is_published: bool = False

class AnnouncementUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    is_published: Optional[bool] = None

class Announcement(BaseModel):
    id: int
    title: str
    content: str
    is_published: bool
    created_date: datetime
    updated_date: datetime
    published_date: Optional[datetime] = None
    created_by_id: int
    created_by: Optional[UserPublic] = None

    model_config = ConfigDict(from_attributes=True)

class AnnouncementListResponse(BaseModel):
    announcements: List[Announcement]
    total: int
    has_more: bool

# ============= PASSWORD RESET SCHEMAS =============

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetVerify(BaseModel):
    token: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, description="New password (min 8 characters)")
    
    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        import re
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/;~`]', v):
            raise ValueError('Password must contain at least one special character')
        return v

class PasswordResetResponse(BaseModel):
    message: str
    success: bool

# ============= FORWARD REFERENCES =============

CollectionTrack.model_rebuild()
CollectionCollaborator.model_rebuild()
Collection.model_rebuild()
CollectionResponse.model_rebuild()
AudioFileResponse.model_rebuild()
FileResponse.model_rebuild()
Announcement.model_rebuild()