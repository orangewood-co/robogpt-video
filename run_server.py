#!/usr/bin/env python3
"""
Main entry point for the video streaming server.
"""
import sys
import os
import signal
import logging

# Add server directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

from server.config import config
from server.app import app, set_recording_service, set_cleanup_manager, stream_manager
from server.recording_service import RecordingService
from server.cleanup_manager import CleanupManager


# Setup logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format=config.log_format,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/server.log')
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Main function to start the server."""
    logger.info("=" * 60)
    logger.info("RoboGPT Video Streaming Server")
    logger.info("=" * 60)

    # Initialize services
    recording_service = None
    cleanup_manager_instance = None

    try:
        # Initialize recording service
        if config.recording_enabled:
            recording_service = RecordingService(
                base_dir='recordings',
                fps=config.recording_fps,
                codec=config.recording_codec
            )
            set_recording_service(recording_service)
            logger.info("Recording service initialized")
        else:
            logger.info("Recording disabled")

        # Initialize cleanup manager
        cleanup_manager_instance = CleanupManager(
            stream_manager=stream_manager,
            recording_service=recording_service,
            config=config
        )
        set_cleanup_manager(cleanup_manager_instance)
        cleanup_manager_instance.start()
        logger.info("Cleanup manager started")

        # Setup graceful shutdown
        def shutdown_handler(signum, frame):
            logger.info("Shutdown signal received")
            if cleanup_manager_instance:
                cleanup_manager_instance.stop()
            if recording_service:
                recording_service.stop_all()
            logger.info("Server stopped gracefully")
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown_handler)
        signal.signal(signal.SIGTERM, shutdown_handler)

        # Print configuration
        logger.info(f"Configuration:")
        logger.info(f"  - Server: {config.server_host}:{config.server_port}")
        logger.info(f"  - Max concurrent streams: {config.max_concurrent_streams}")
        logger.info(f"  - Stream timeout: {config.stream_timeout}s")
        logger.info(f"  - Recording: {'Enabled' if config.recording_enabled else 'Disabled'}")
        if config.recording_enabled:
            logger.info(f"  - Recording codec: {config.recording_codec}")
            logger.info(f"  - Recording FPS: {config.recording_fps}")
            logger.info(f"  - Retention: {config.retention_days} days")
        logger.info(f"  - CORS: {'Enabled' if config.cors_enabled else 'Disabled'}")

        # Start Flask server
        logger.info("=" * 60)
        logger.info(f"Server starting on http://{config.server_host}:{config.server_port}")
        logger.info("Endpoints:")
        logger.info(f"  - POST   /publish/<stream_name>")
        logger.info(f"  - GET    /stream/<stream_name>")
        logger.info(f"  - GET    /api/streams")
        logger.info(f"  - GET    /api/streams/<stream_name>/stats")
        logger.info(f"  - DELETE /api/streams/<stream_name>")
        logger.info(f"  - GET    /health")
        logger.info("=" * 60)

        # Run the Flask app
        app.run(
            host=config.server_host,
            port=config.server_port,
            debug=config.server_debug,
            threaded=True
        )

    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        return 1
    finally:
        # Cleanup
        if cleanup_manager_instance:
            cleanup_manager_instance.stop()
        if recording_service:
            recording_service.stop_all()

    return 0


if __name__ == '__main__':
    sys.exit(main())
