from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import crud, models
from app.core.storage import minio_client
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_expired_revoked_tokens(db: Session):
    """remove expired tokens from the revoked tokens blacklist"""
    try:
        deleted_count = crud.cleanup_expired_tokens(db)
        logger.info(f"Cleaned up {deleted_count} expired revoked tokens")
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up revoked tokens: {e}")
        return 0


def cleanup_old_audit_logs(db: Session, retention_days: int = 3650):
    """
    clean up old audit logs
    """
    try:
        deleted_count = crud.cleanup_old_audit_logs(db, retention_days)
        logger.info(f"Cleaned up {deleted_count} audit logs older than {retention_days} days")
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up audit logs: {e}")
        return 0


def process_pending_deletions(db: Session):
    """
    process pending user deletion requests that have passed the grace period
    """
    try:
        pending_deletions = crud.get_pending_deletions(db)
        processed_count = 0

        for deletion_request in pending_deletions:
            user = crud.get_user(db, deletion_request.user_id)
            if not user:
                #user already deleted => mark as completed
                crud.complete_deletion_request(db, deletion_request.id)
                continue

            logger.info(f"Processing {deletion_request.deletion_type} deletion for user {user.username} (ID: {user.id})")

            #log deletion
            crud.create_audit_log(
                db=db,
                action=f"user.{deletion_request.deletion_type}_delete_automated",
                user_id=user.id,
                resource_type="user",
                resource_id=str(user.id),
                details=f"Automated {deletion_request.deletion_type} deletion after grace period. Reason: {deletion_request.reason}",
                success=True
            )

            #perform deletion
            if deletion_request.deletion_type == "soft":
                crud.soft_delete_user(db, user.id)
            elif deletion_request.deletion_type == "hard":
                crud.hard_delete_user(db, user.id)

            #mark request as completed
            crud.complete_deletion_request(db, deletion_request.id)
            processed_count += 1

        logger.info(f"Processed {processed_count} pending deletions")
        return processed_count

    except Exception as e:
        logger.error(f"Error processing pending deletions: {e}")
        return 0


def cleanup_unused_profile_pictures(db: Session):
    """
    clean up profile pictures from MinIO that are no longer referenced in database
    """
    try:
        bucket_name = settings.MINIO_BUCKET_NAME  #"profile-pictures"

        #get all profile picture URLs from the database
        users_with_profile_pics = db.query(models.User.profile_picture_url).filter(
            models.User.profile_picture_url.isnot(None)
        ).all()

        #extract just the filenames from the URLs
        referenced_filenames = set()
        for (url,) in users_with_profile_pics:
            if url:
                #URL format: http://{MINIO_ENDPOINT}/{BUCKET_NAME}/{filename}
                filename = url.split("/")[-1]
                referenced_filenames.add(filename)

        logger.info(f"Found {len(referenced_filenames)} profile pictures referenced in database")

        #list all objects in the profile-pictures bucket
        objects_in_bucket = minio_client.list_objects(bucket_name, recursive=True)

        deleted_count = 0
        error_count = 0

        for obj in objects_in_bucket:
            filename = obj.object_name
            if filename not in referenced_filenames:
                try:
                    minio_client.remove_object(bucket_name, filename)
                    logger.info(f"Deleted orphaned profile picture: {filename}")
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Failed to delete orphaned profile picture {filename}: {e}")
                    error_count += 1

        logger.info(f"Profile picture cleanup complete: deleted {deleted_count}, errors: {error_count}")
        return {"deleted": deleted_count, "errors": error_count}

    except Exception as e:
        logger.error(f"Error cleaning up unused profile pictures: {e}")
        return {"deleted": 0, "errors": 1, "error_message": str(e)}
    
def cleanup_expired_reset_tokens(db: Session):
    """remove expired password reset tokens"""
    try:
        deleted_count = crud.cleanup_expired_reset_tokens(db)
        logger.info(f"Cleaned up {deleted_count} expired password reset tokens")
        return deleted_count
    except Exception as e:
        logger.error(f"Error cleaning up password reset tokens: {e}")
        return 0

def initialize_default_retention_policies(db: Session):
    default_policies = [
        {
            "data_type": "audit_logs",
            "retention_days": 3650,  #10 years
            "description": "Audit logs must be kept for 10 years"
        },
        {
            "data_type": "user_data",
            "retention_days": 1095,  #3 years after last activity
            "description": "User data retained for 3 years after last activity, then soft deleted"
        },
        {
            "data_type": "audio_files",
            "retention_days": 730,  #2 years for inactive accounts
            "description": "Audio files for inactive accounts retained for 2 years"
        },
        {
            "data_type": "revoked_tokens",
            "retention_days": 7,  #7 days after expiration
            "description": "Revoked tokens cleaned up 7 days after expiration"
        },
        {
            "data_type": "deletion_requests",
            "retention_days": 365,  #1 year
            "description": "Completed deletion requests kept for 1 year for audit purposes"
        }
    ]

    for policy in default_policies:
        try:
            crud.create_retention_policy(
                db=db,
                data_type=policy["data_type"],
                retention_days=policy["retention_days"],
                description=policy["description"]
            )
            logger.info(f"Created retention policy for {policy['data_type']}: {policy['retention_days']} days")
        except Exception as e:
            logger.warning(f"Policy for {policy['data_type']} may already exist: {e}")


def run_all_cleanup_tasks():
    """
    run all data retention cleanup tasks
    """
    db = SessionLocal()
    try:
        logger.info("=" * 80)
        logger.info("Starting data retention cleanup tasks")
        logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        logger.info("=" * 80)

        logger.info("\n1. Cleaning up expired revoked tokens...")
        cleanup_expired_revoked_tokens(db)

        logger.info("\n2. Processing pending user deletions...")
        process_pending_deletions(db)

        logger.info("\n3. Cleaning up old audit logs (10 year retention)...")
        cleanup_old_audit_logs(db, retention_days=3650)

        logger.info("\n4. Cleaning up unused profile pictures...")
        cleanup_unused_profile_pictures(db)

        logger.info("\n5. Ensuring default retention policies exist...")
        initialize_default_retention_policies(db)

        logger.info("\n6. Cleaning up expired password reset tokens...")
        cleanup_expired_reset_tokens(db)

        logger.info("\n" + "=" * 80)
        logger.info("Data retention cleanup tasks completed successfully")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error running cleanup tasks: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    run_all_cleanup_tasks()