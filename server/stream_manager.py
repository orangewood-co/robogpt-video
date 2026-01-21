"""
Stream management with thread-safe operations.
"""
import threading
import logging
import re
from datetime import datetime
from collections import deque
from typing import Dict, Optional, Generator, List
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class StreamInfo:
    """Information about an active stream."""
    name: str
    created_at: datetime = field(default_factory=datetime.now)
    last_frame_time: datetime = field(default_factory=datetime.now)
    current_frame: Optional[bytes] = None
    frame_buffer: deque = field(default_factory=lambda: deque(maxlen=30))
    viewer_count: int = 0
    total_frames: int = 0


class StreamManager:
    """
    Central hub for managing video streams.
    Thread-safe stream creation, deletion, and frame management.
    """

    def __init__(self, max_concurrent: int = 50, max_buffer_frames: int = 30):
        """
        Initialize stream manager.

        Args:
            max_concurrent: Maximum number of concurrent streams
            max_buffer_frames: Maximum frames to buffer per stream
        """
        self._streams: Dict[str, StreamInfo] = {}
        self._lock = threading.RLock()
        self.max_concurrent = max_concurrent
        self.max_buffer_frames = max_buffer_frames

        logger.info(f"StreamManager initialized (max_concurrent={max_concurrent}, "
                   f"max_buffer_frames={max_buffer_frames})")

    def _validate_stream_name(self, name: str) -> bool:
        """
        Validate stream name format.

        Args:
            name: Stream name to validate

        Returns:
            True if valid, False otherwise
        """
        # Allow alphanumeric, underscore, dash (1-64 chars)
        pattern = r'^[a-zA-Z0-9_-]{1,64}$'
        return bool(re.match(pattern, name))

    def create_stream(self, name: str) -> bool:
        """
        Create a new stream if it doesn't exist.

        Args:
            name: Stream name

        Returns:
            True if created, False if already exists or invalid name

        Raises:
            ValueError: If stream name is invalid
            RuntimeError: If max concurrent streams reached
        """
        if not self._validate_stream_name(name):
            raise ValueError(f"Invalid stream name: {name}. Use alphanumeric, underscore, or dash only")

        with self._lock:
            if name in self._streams:
                logger.debug(f"Stream already exists: {name}")
                return False

            if len(self._streams) >= self.max_concurrent:
                raise RuntimeError(f"Maximum concurrent streams ({self.max_concurrent}) reached")

            # Create stream with custom buffer size
            stream = StreamInfo(
                name=name,
                frame_buffer=deque(maxlen=self.max_buffer_frames)
            )
            self._streams[name] = stream

            logger.info(f"Stream created: {name}")
            return True

    def publish_frame(self, name: str, frame_data: bytes) -> bool:
        """
        Publish a new frame to a stream.

        Args:
            name: Stream name
            frame_data: JPEG frame data

        Returns:
            True if successful, False if stream doesn't exist
        """
        with self._lock:
            if name not in self._streams:
                logger.warning(f"Attempted to publish to non-existent stream: {name}")
                return False

            stream = self._streams[name]
            stream.current_frame = frame_data
            stream.frame_buffer.append(frame_data)
            stream.last_frame_time = datetime.now()
            stream.total_frames += 1

            logger.debug(f"Frame published to {name} (total: {stream.total_frames})")
            return True

    def get_current_frame(self, name: str) -> Optional[bytes]:
        """
        Get the most recent frame from a stream.

        Args:
            name: Stream name

        Returns:
            Frame data or None if stream doesn't exist
        """
        with self._lock:
            if name not in self._streams:
                return None
            return self._streams[name].current_frame

    def get_stream_generator(self, name: str) -> Generator[bytes, None, None]:
        """
        Get an MJPEG stream generator for a stream.

        Args:
            name: Stream name

        Yields:
            MJPEG multipart frames
        """
        logger.info(f"Starting stream generator for: {name}")

        # Increment viewer count
        with self._lock:
            if name in self._streams:
                self._streams[name].viewer_count += 1

        try:
            while True:
                frame = self.get_current_frame(name)
                if frame:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                else:
                    # Stream doesn't exist or no frame yet
                    # Send a small delay to prevent tight loop
                    import time
                    time.sleep(0.1)

        finally:
            # Decrement viewer count when generator stops
            with self._lock:
                if name in self._streams:
                    self._streams[name].viewer_count -= 1
                    logger.info(f"Viewer disconnected from {name} "
                              f"(remaining: {self._streams[name].viewer_count})")

    def stream_exists(self, name: str) -> bool:
        """
        Check if a stream exists.

        Args:
            name: Stream name

        Returns:
            True if stream exists
        """
        with self._lock:
            return name in self._streams

    def delete_stream(self, name: str) -> bool:
        """
        Delete a stream.

        Args:
            name: Stream name

        Returns:
            True if deleted, False if didn't exist
        """
        with self._lock:
            if name not in self._streams:
                return False

            del self._streams[name]
            logger.info(f"Stream deleted: {name}")
            return True

    def get_inactive_streams(self, timeout_seconds: int) -> List[str]:
        """
        Get list of streams that have been inactive.

        Args:
            timeout_seconds: Inactivity threshold in seconds

        Returns:
            List of inactive stream names
        """
        inactive = []
        now = datetime.now()

        with self._lock:
            for name, stream in self._streams.items():
                elapsed = (now - stream.last_frame_time).total_seconds()
                if elapsed >= timeout_seconds:
                    inactive.append(name)

        return inactive

    def cleanup_inactive_streams(self, timeout_seconds: int) -> int:
        """
        Remove inactive streams.

        Args:
            timeout_seconds: Inactivity threshold in seconds

        Returns:
            Number of streams cleaned up
        """
        inactive = self.get_inactive_streams(timeout_seconds)

        for name in inactive:
            self.delete_stream(name)
            logger.info(f"Cleaned up inactive stream: {name}")

        return len(inactive)

    def get_stats(self, name: str) -> Optional[Dict]:
        """
        Get statistics for a stream.

        Args:
            name: Stream name

        Returns:
            Stream statistics or None if doesn't exist
        """
        with self._lock:
            if name not in self._streams:
                return None

            stream = self._streams[name]
            now = datetime.now()
            uptime = (now - stream.created_at).total_seconds()
            inactive_time = (now - stream.last_frame_time).total_seconds()

            return {
                'name': stream.name,
                'created_at': stream.created_at.isoformat(),
                'uptime_seconds': uptime,
                'last_frame_time': stream.last_frame_time.isoformat(),
                'inactive_seconds': inactive_time,
                'total_frames': stream.total_frames,
                'viewer_count': stream.viewer_count,
                'buffer_size': len(stream.frame_buffer),
                'has_current_frame': stream.current_frame is not None
            }

    def get_all_streams_stats(self) -> List[Dict]:
        """
        Get statistics for all streams.

        Returns:
            List of stream statistics
        """
        with self._lock:
            stream_names = list(self._streams.keys())

        return [self.get_stats(name) for name in stream_names]

    def get_stream_count(self) -> int:
        """
        Get current number of active streams.

        Returns:
            Number of active streams
        """
        with self._lock:
            return len(self._streams)
