"""
Background cleanup manager for inactive streams and old recordings.
"""
import os
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger


logger = logging.getLogger(__name__)


class CleanupManager:
    """
    Manager for background cleanup tasks.
    """

    def __init__(self, stream_manager, recording_service, config):
        """
        Initialize cleanup manager.

        Args:
            stream_manager: StreamManager instance
            recording_service: RecordingService instance
            config: Configuration object
        """
        self.stream_manager = stream_manager
        self.recording_service = recording_service
        self.config = config

        self.scheduler = BackgroundScheduler()
        self.is_running = False

        logger.info("CleanupManager initialized")

    def start(self):
        """Start background cleanup tasks."""
        if self.is_running:
            logger.warning("CleanupManager already running")
            return

        # Schedule inactive stream cleanup
        cleanup_interval = self.config.cleanup_interval
        self.scheduler.add_job(
            self._cleanup_inactive_streams,
            trigger=IntervalTrigger(seconds=cleanup_interval),
            id='cleanup_inactive_streams',
            name='Cleanup inactive streams',
            replace_existing=True
        )
        logger.info(f"Scheduled inactive stream cleanup every {cleanup_interval}s")

        # Schedule old recordings cleanup
        schedule_time = self.config.cleanup_schedule_time
        try:
            hour, minute = map(int, schedule_time.split(':'))
            self.scheduler.add_job(
                self._cleanup_old_recordings,
                trigger=CronTrigger(hour=hour, minute=minute),
                id='cleanup_old_recordings',
                name='Cleanup old recordings',
                replace_existing=True
            )
            logger.info(f"Scheduled old recordings cleanup daily at {schedule_time}")
        except ValueError as e:
            logger.error(f"Invalid cleanup schedule time '{schedule_time}': {e}")

        # Start the scheduler
        self.scheduler.start()
        self.is_running = True
        logger.info("CleanupManager started")

    def stop(self):
        """Stop background cleanup tasks."""
        if not self.is_running:
            return

        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("CleanupManager stopped")

    def _cleanup_inactive_streams(self):
        """Clean up inactive streams."""
        try:
            timeout = self.config.stream_timeout
            inactive_streams = self.stream_manager.get_inactive_streams(timeout)

            if not inactive_streams:
                logger.debug("No inactive streams to clean up")
                return

            logger.info(f"Found {len(inactive_streams)} inactive streams")

            for stream_name in inactive_streams:
                # Stop recording first
                if self.recording_service:
                    self.recording_service.stop_recording(stream_name)

                # Delete stream
                self.stream_manager.delete_stream(stream_name)
                logger.info(f"Cleaned up inactive stream: {stream_name}")

            logger.info(f"Cleaned up {len(inactive_streams)} inactive streams")

        except Exception as e:
            logger.error(f"Error during inactive stream cleanup: {e}", exc_info=True)

    def _cleanup_old_recordings(self):
        """Clean up old recordings based on retention policy."""
        try:
            retention_days = self.config.retention_days
            base_dir = Path('recordings')

            if not base_dir.exists():
                logger.debug("Recordings directory does not exist")
                return

            cutoff_time = datetime.now() - timedelta(days=retention_days)
            deleted_count = 0
            deleted_size = 0

            logger.info(f"Starting cleanup of recordings older than {retention_days} days")

            # Walk through all files in recordings directory
            for file_path in base_dir.rglob('*'):
                if not file_path.is_file():
                    continue

                try:
                    # Check file modification time
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)

                    if mtime < cutoff_time:
                        # Get file size before deletion
                        file_size = file_path.stat().st_size

                        # Delete the file
                        file_path.unlink()
                        deleted_count += 1
                        deleted_size += file_size

                        logger.info(f"Deleted old recording: {file_path}")

                except Exception as e:
                    logger.error(f"Error deleting file {file_path}: {e}")

            # Clean up empty directories
            self._cleanup_empty_directories(base_dir)

            if deleted_count > 0:
                deleted_mb = deleted_size / (1024 * 1024)
                logger.info(f"Cleanup complete: deleted {deleted_count} files ({deleted_mb:.2f} MB)")
            else:
                logger.info("No old recordings to clean up")

        except Exception as e:
            logger.error(f"Error during old recordings cleanup: {e}", exc_info=True)

    def _cleanup_empty_directories(self, base_dir: Path):
        """
        Remove empty directories recursively.

        Args:
            base_dir: Base directory to clean
        """
        try:
            for dir_path in sorted(base_dir.rglob('*'), reverse=True):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    dir_path.rmdir()
                    logger.debug(f"Removed empty directory: {dir_path}")
        except Exception as e:
            logger.error(f"Error cleaning up empty directories: {e}")

    def run_cleanup_now(self):
        """Manually trigger cleanup tasks immediately."""
        logger.info("Manual cleanup triggered")
        self._cleanup_inactive_streams()
        self._cleanup_old_recordings()
        logger.info("Manual cleanup completed")

    def get_next_run_times(self):
        """
        Get next scheduled run times for cleanup jobs.

        Returns:
            Dictionary with job names and next run times
        """
        jobs = {}
        for job in self.scheduler.get_jobs():
            jobs[job.name] = job.next_run_time.isoformat() if job.next_run_time else None

        return jobs
