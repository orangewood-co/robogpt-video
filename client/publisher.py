"""
Generic stream publisher client.
"""
import cv2
import requests
import logging
import threading
import queue
import time
from typing import Optional
import numpy as np


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StreamPublisher:
    """
    Generic reusable stream publisher with automatic reconnection.
    """

    def __init__(self, server_url: str, stream_name: str, quality: int = 85,
                 max_fps: int = 30, retry_delay: int = 5):
        """
        Initialize stream publisher.

        Args:
            server_url: Base URL of the streaming server (e.g., http://localhost:5000)
            stream_name: Name of the stream
            quality: JPEG compression quality (0-100)
            max_fps: Maximum frames per second to send
            retry_delay: Seconds to wait before retrying failed connection
        """
        self.server_url = server_url.rstrip('/')
        self.stream_name = stream_name
        self.quality = quality
        self.max_fps = max_fps
        self.retry_delay = retry_delay

        self.publish_url = f"{self.server_url}/publish/{self.stream_name}"

        self.frame_queue = queue.Queue(maxsize=60)
        self.stop_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None

        self.frame_interval = 1.0 / max_fps if max_fps > 0 else 0
        self.total_frames = 0
        self.failed_frames = 0

        logger.info(f"StreamPublisher initialized for '{stream_name}' at {server_url}")

    def start(self):
        """Start the publisher worker thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            logger.warning("Publisher already running")
            return

        self.stop_event.clear()
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info(f"Publisher started for stream: {self.stream_name}")

    def stop(self):
        """Stop the publisher worker thread."""
        self.stop_event.set()
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info(f"Publisher stopped for stream: {self.stream_name}")

    def publish_frame(self, frame: np.ndarray) -> bool:
        """
        Publish a frame to the stream (non-blocking).

        Args:
            frame: OpenCV frame (numpy array)

        Returns:
            True if frame was queued, False if queue is full
        """
        try:
            self.frame_queue.put(frame, block=False)
            return True
        except queue.Full:
            logger.warning("Frame queue full, dropping frame")
            return False

    def _encode_frame(self, frame: np.ndarray) -> Optional[bytes]:
        """
        Encode frame to JPEG.

        Args:
            frame: OpenCV frame

        Returns:
            JPEG bytes or None if encoding failed
        """
        try:
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.quality]
            success, buffer = cv2.imencode('.jpg', frame, encode_params)

            if not success:
                logger.error("Failed to encode frame to JPEG")
                return None

            return buffer.tobytes()

        except Exception as e:
            logger.error(f"Error encoding frame: {e}")
            return None

    def _send_frame(self, frame_data: bytes) -> bool:
        """
        Send encoded frame to server.

        Args:
            frame_data: JPEG frame bytes

        Returns:
            True if successful, False otherwise
        """
        try:
            files = {'frame': ('frame.jpg', frame_data, 'image/jpeg')}
            response = requests.post(self.publish_url, files=files, timeout=5)

            if response.status_code == 200:
                return True
            else:
                logger.warning(f"Server returned status {response.status_code}: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send frame: {e}")
            return False

    def _worker_loop(self):
        """Main worker loop for sending frames."""
        logger.info(f"Publisher worker started for {self.stream_name}")
        last_frame_time = 0

        while not self.stop_event.is_set():
            try:
                # Get frame from queue with timeout
                frame = self.frame_queue.get(timeout=1)

                # Rate limiting
                if self.frame_interval > 0:
                    elapsed = time.time() - last_frame_time
                    if elapsed < self.frame_interval:
                        time.sleep(self.frame_interval - elapsed)

                # Encode frame
                frame_data = self._encode_frame(frame)
                if frame_data is None:
                    self.failed_frames += 1
                    continue

                # Send frame
                success = self._send_frame(frame_data)

                if success:
                    self.total_frames += 1
                    last_frame_time = time.time()
                else:
                    self.failed_frames += 1
                    # Wait before retry on failure
                    time.sleep(self.retry_delay)

            except queue.Empty:
                # No frames in queue, continue waiting
                continue
            except Exception as e:
                logger.error(f"Error in publisher worker: {e}", exc_info=True)
                time.sleep(self.retry_delay)

        logger.info(f"Publisher worker stopped (total: {self.total_frames}, failed: {self.failed_frames})")

    def get_stats(self) -> dict:
        """
        Get publisher statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            'stream_name': self.stream_name,
            'total_frames': self.total_frames,
            'failed_frames': self.failed_frames,
            'queue_size': self.frame_queue.qsize(),
            'is_running': self.worker_thread and self.worker_thread.is_alive()
        }
