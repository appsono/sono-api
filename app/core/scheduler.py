from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import logging

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = BackgroundScheduler(
    timezone="UTC",
    job_defaults={
        'coalesce': True,
        'max_instances': 1,
        'misfire_grace_time': 3600
    }
)


def job_listener(event):
    if event.exception:
        logger.error(f"Job {event.job_id} failed with exception: {event.exception}")
    else:
        logger.info(f"Job {event.job_id} executed successfully")


def run_cleanup_job():
    from app.tasks.data_retention import run_all_cleanup_tasks

    logger.info("Starting scheduled cleanup tasks...")
    try:
        run_all_cleanup_tasks()
        logger.info("Scheduled cleanup tasks completed successfully")
    except Exception as e:
        logger.error(f"Error running scheduled cleanup tasks: {e}")


def run_pending_deletions_job():
    from app.database import SessionLocal
    from app.tasks.data_retention import process_pending_deletions

    logger.info("Processing pending user deletions...")
    db = SessionLocal()
    try:
        processed = process_pending_deletions(db)
        logger.info(f"Processed {processed} pending deletions")
    except Exception as e:
        logger.error(f"Error processing pending deletions: {e}")
    finally:
        db.close()


def init_scheduler():
    scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    scheduler.add_job(
        run_cleanup_job,
        trigger=CronTrigger(
            day_of_week='mon',
            hour=3,
            minute=0
        ),
        id='weekly_cleanup',
        name='Weekly Data Retention Cleanup',
        replace_existing=True
    )

    scheduler.add_job(
        run_pending_deletions_job,
        trigger=CronTrigger(
            hour=4,
            minute=0
        ),
        id='daily_pending_deletions',
        name='Daily Pending Deletions Processing',
        replace_existing=True
    )

    logger.info("Scheduler initialized with cleanup jobs")
    logger.info("  - Weekly cleanup: Mondays at 03:00 UTC")
    logger.info("  - Pending deletions: Daily at 04:00 UTC")


def start_scheduler():
    if not scheduler.running:
        scheduler.start()
        logger.info("Background scheduler started")


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Background scheduler stopped")


def get_scheduled_jobs():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        })
    return jobs