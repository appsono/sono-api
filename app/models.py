from sqlalchemy import Boolean, Column, Integer, String, ForeignKey, DateTime, Text, UniqueConstraint, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

# ============= ENUMS =============

class CollectionType(str, enum.Enum):
    ALBUM = "album"
    PLAYLIST = "playlist"
    COMPILATION = "compilation"

# ============= USER MODEL =============

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    profile_picture_url = Column(String, nullable=True)

    #timestamp for when user account was created
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    #audio upload limit field
    max_audio_uploads = Column(Integer, default=20)

    display_name = Column(String, nullable=True)
    bio = Column(String, nullable=True)

    #existing relationships
    files = relationship("File", back_populates="owner")
    audio_files = relationship("AudioFile", back_populates="owner")
    
    collections = relationship("Collection", back_populates="owner", cascade="all, delete-orphan")
    
    #collection collaboration relationships
    collection_collaborations = relationship(
        "CollectionCollaborator", 
        foreign_keys="CollectionCollaborator.user_id",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    added_collaborations = relationship(
        "CollectionCollaborator", 
        foreign_keys="CollectionCollaborator.added_by_id",
        back_populates="added_by"
    )
    
    #collection tracks added by this user
    added_collection_tracks = relationship(
        "CollectionTrack", 
        foreign_keys="CollectionTrack.added_by_id",
        back_populates="added_by"
    )

    def get_albums(self):
        return [c for c in self.collections if c.collection_type == CollectionType.ALBUM]

    def get_playlists(self):
        return [c for c in self.collections if c.collection_type == CollectionType.PLAYLIST]

    def get_compilations(self):
        return [c for c in self.collections if c.collection_type == CollectionType.COMPILATION]

    def get_collection_stats(self):
        albums = self.get_albums()
        playlists = self.get_playlists()
        compilations = self.get_compilations()
        
        return {
            "total_collections": len(self.collections),
            "albums_count": len(albums),
            "playlists_count": len(playlists),
            "compilations_count": len(compilations),
            "collaborative_count": len([c for c in self.collections if c.is_collaborative]),
            "public_count": len([c for c in self.collections if c.is_public])
        }

    def can_create_collection(self, collection_type=None):
        return True

    def get_collaborative_collections(self):
        return [collab.collection for collab in self.collection_collaborations]

    def get_all_accessible_collections(self):
        owned = self.collections
        collaborative = self.get_collaborative_collections()
        return list(set(owned + collaborative))

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    content_type = Column(String)
    upload_date = Column(String)
    file_url = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="files")

class AudioFile(Base):
    __tablename__ = "audio_files"

    id = Column(Integer, primary_key=True, index=True)
    original_filename = Column(String, index=True)
    stored_filename = Column(String, unique=True, index=True)
    title = Column(String, nullable=True)
    description = Column(String, nullable=True)
    file_size = Column(Integer)
    duration = Column(Integer, nullable=True)
    content_type = Column(String)
    file_url = Column(String)
    upload_date = Column(DateTime, default=datetime.utcnow)
    is_public = Column(Boolean, default=False)
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    owner = relationship("User", back_populates="audio_files")
    collection_tracks = relationship("CollectionTrack", back_populates="audio_file")

    def get_collection_appearances(self):
        return [track.collection for track in self.collection_tracks]

    def is_in_collection(self, collection_id):
        return any(track.collection_id == collection_id for track in self.collection_tracks)

# ============= UNIFIED COLLECTIONS MODELS =============

class Collection(Base):
    __tablename__ = "collections"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    collection_type = Column(Enum(CollectionType, values_callable=lambda x: [e.value for e in x]), nullable=False, index=True)
    
    artist = Column(String(100), nullable=True)  #primarily for albums
    curator_note = Column(Text, nullable=True)   #primarily for compilations
    
    cover_art_url = Column(String, nullable=True)
    is_public = Column(Boolean, default=False, nullable=False)
    is_collaborative = Column(Boolean, default=False, nullable=False)  #can be used by any type
    
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    #foreign key to user (collection owner/creator)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    #relationships
    owner = relationship("User", back_populates="collections")
    tracks = relationship("CollectionTrack", back_populates="collection", cascade="all, delete-orphan", order_by="CollectionTrack.track_order")
    collaborators = relationship("CollectionCollaborator", back_populates="collection", cascade="all, delete-orphan")

    @property
    def is_album(self) -> bool:
        return self.collection_type == CollectionType.ALBUM

    @property
    def is_playlist(self) -> bool:
        return self.collection_type == CollectionType.PLAYLIST

    @property
    def is_compilation(self) -> bool:
        return self.collection_type == CollectionType.COMPILATION

    @property
    def track_count(self) -> int:
        return len(self.tracks)

    def get_ordered_tracks(self):
        return sorted(self.tracks, key=lambda t: t.track_order)

    def can_user_view(self, user_id: int) -> bool:
        if self.owner_id == user_id or self.is_public:
            return True
        return any(c.user_id == user_id for c in self.collaborators)

    def can_user_edit(self, user_id: int) -> bool:
        if self.owner_id == user_id:
            return True
        if self.is_collaborative:
            return any(c.user_id == user_id and c.permission_level == "edit" for c in self.collaborators)
        return False

class CollectionTrack(Base):
    __tablename__ = "collection_tracks"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False)
    audio_file_id = Column(Integer, ForeignKey("audio_files.id"), nullable=False)
    track_order = Column(Integer, nullable=False)  #universal ordering
    added_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    added_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)  #for collaboration tracking
    
    #relationships
    collection = relationship("Collection", back_populates="tracks")
    audio_file = relationship("AudioFile", back_populates="collection_tracks")
    added_by = relationship("User", foreign_keys=[added_by_id])
    
    #ensure unique track orders per collection
    __table_args__ = (UniqueConstraint('collection_id', 'track_order', name='uq_collection_track_order'),)

class CollectionCollaborator(Base):
    __tablename__ = "collection_collaborators"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    permission_level = Column(String(20), default="edit", nullable=False)  #"edit" or "view"
    added_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    added_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)  #who added this collaborator
    
    #relationships
    collection = relationship("Collection", back_populates="collaborators")
    user = relationship("User", foreign_keys=[user_id], back_populates="collection_collaborations")
    added_by = relationship("User", foreign_keys=[added_by_id], back_populates="added_collaborations")
    
    #ensure unique collaborator per collection
    __table_args__ = (UniqueConstraint('collection_id', 'user_id', name='uq_collection_collaborator'),)

# ============= NEWS/ANNOUNCEMENTS MODEL =============

class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    is_published = Column(Boolean, default=False, nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    published_date = Column(DateTime, nullable=True)

    #admin who created it
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by = relationship("User", foreign_keys=[created_by_id])

# ============= SECURITY & COMPLIANCE MODELS =============

class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String, unique=True, index=True, nullable=False)  #JWT ID (token identifier)
    token = Column(Text, nullable=False)  #full token for verification
    token_type = Column(String(20), nullable=False)  #"access" or "refresh"
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    revoked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)  #when the token would have expired
    reason = Column(String, nullable=True)  #"logout", "password_change", "admin_revoke", etc.

    user = relationship("User")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  #nullable for system actions
    action = Column(String, nullable=False, index=True)  #e.g. "user.delete", "data.export", "login.success"
    resource_type = Column(String, nullable=True)  #e.g. "user", "audio_file", "collection"
    resource_id = Column(String, nullable=True)  #ID of affected resource
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    details = Column(Text, nullable=True)  #JSON or text details
    success = Column(Boolean, default=True, nullable=False)

    user = relationship("User")

class UserConsent(Base):
    __tablename__ = "user_consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    consent_type = Column(String, nullable=False)  #e.g. "terms_of_service", "privacy_policy", "data_processing"
    consent_version = Column(String, nullable=False)  #version of terms/policy
    given_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ip_address = Column(String, nullable=True)
    withdrawn_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    user = relationship("User")

    __table_args__ = (UniqueConstraint('user_id', 'consent_type', 'consent_version', name='uq_user_consent'),)

class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policies"

    id = Column(Integer, primary_key=True, index=True)
    data_type = Column(String, unique=True, nullable=False)  #e.g., "audio_files", "user_data", "audit_logs"
    retention_days = Column(Integer, nullable=False)  #how many days to keep the data
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class UserDeletionRequest(Base):
    __tablename__ = "user_deletion_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    scheduled_deletion_at = Column(DateTime, nullable=False)  #when deletion will occur (grace period)
    deletion_type = Column(String(20), nullable=False)  #"soft" or "hard"
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="pending", nullable=False)  #"pending", "completed", "cancelled"
    reason = Column(Text, nullable=True)  #user's reason for deletion

    user = relationship("User")

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    is_valid = Column(Boolean, default=True, nullable=False)
    ip_address = Column(String, nullable=True)

    user = relationship("User")