"""
Celery Beat — periodic task schedule.
"""

from celery import Celery
from celery.schedules import crontab
from config import settings

beat_app = Celery(
    "ultrasearch_beat",
    broker=settings.redis_url,
)

beat_app.conf.beat_schedule = {
    # Re-crawl seed URLs that are overdue — every hour
    "recrawl-due-seeds": {
        "task":     "workers.tasks.recrawl_due_seeds",
        "schedule": crontab(minute=0),   # top of every hour
    },
    # Purge old research reports — every Sunday at 3 AM
    "purge-old-reports": {
        "task":     "workers.tasks.purge_old_reports",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
        "kwargs":   {"days": 30},
    },
    # Evict expired memory sessions — every 15 minutes
    "evict-sessions": {
        "task":     "workers.tasks.evict_sessions",
        "schedule": crontab(minute="*/15"),
    },
}

beat_app.conf.timezone = "UTC"
