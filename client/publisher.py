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
    Generic reusable stream publisher with automatic reconnection and adaptive rate control.
    """

    def __init__(self, server_url: str, stream_name: str, quality: int = 85,
                 max_fps: int = 30, retry_delay: int = 5, adaptive: bool = True,
                 max_queue_size: int = 30):
        """
        Initialize stream publisher.

        Args:
            server_url: Base URL of the streaming server (e.g., http://localhost:5000)
            stream_name: Name of the stream
            quality: JPEG compression quality (0-100)
            max_fps: Maximum frames per second to send
            retry_delay: Seconds to wait before retrying failed connection
            adaptive: Enable adaptive rate control based on network conditions
            max_queue_size: Maximum frames to queue before dropping
        """
        self.server_url = server_url.rstrip('/')
        self.stream_name = stream_name
        self.base_quality = quality
        self.quality = quality
        self.max_fps = max_fps
        self.retry_delay = retry_delay
        self.adaptive = adaptive
        self.max_queue_size = max_queue_size

        self.publish_url = f"{self.server_url}/publish/{self.stream_name}"

        self.frame_queue = queue.Queue(maxsize=max_queue_size)
        self.stop_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None

        self.frame_interval = 1.0 / max_fps if max_fps > 0 else 0
        self.total_frames = 0
        self.failed_frames = 0
        self.dropped_frames = 0
        self.skipped_frames = 0

        # Adaptive control
        self.last_send_time = 0
        self.send_times = []  # Track recent send times for adaptive control

        logger.info(f"StreamPublisher initialized for '{stream_name}' at {server_url} "
                   f"(adaptive={adaptive}, max_queue={max_queue_size})")

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
        Publish a frame to the stream (non-blocking) with adaptive frame skipping.

        Args:
            frame: OpenCV frame (numpy array)

        Returns:
            True if frame was queued, False if queue is full or frame was skipped
        """
        if self.adaptive:
            queue_size = self.frame_queue.qsize()
            queue_utilization = queue_size / self.max_queue_size

            # Skip frames if queue is filling up (>70% full)
            if queue_utilization > 0.7:
                # Skip frame probabilistically based on queue fullness
                skip_probability = (queue_utilization - 0.7) / 0.3  # 0 to 1 as queue fills
                if time.time() % 1.0 < skip_probability:
                    self.skipped_frames += 1
                    if self.skipped_frames % 10 == 0:  # Log every 10 skips
                        logger.debug(f"Skipping frame (queue {queue_utilization:.0%} full, "
                                   f"total skipped: {self.skipped_frames})")
                    return False

        try:
            self.frame_queue.put(frame, block=False)
            return True
        except queue.Full:
            self.dropped_frames += 1
            if self.dropped_frames % 10 == 0:  # Log every 10 drops
                logger.warning(f"Frame queue full, dropped {self.dropped_frames} frames total")
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
        Send encoded frame to server with timing tracking.

        Args:
            frame_data: JPEG frame bytes

        Returns:
            True if successful, False otherwise
        """
        try:
            start_time = time.time()
            files = {'frame': ('frame.jpg', frame_data, 'image/jpeg')}
            response = requests.post(self.publish_url, files=files, timeout=10)

            send_duration = time.time() - start_time

            # Track send times for adaptive control
            if self.adaptive:
                self.send_times.append(send_duration)
                # Keep only last 10 send times
                if len(self.send_times) > 10:
                    self.send_times.pop(0)

            if response.status_code == 200:
                return True
            else:
                logger.warning(f"Server returned status {response.status_code}: {response.text}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send frame: {e}")
            return False

    def _adapt_quality(self):
        """Adapt JPEG quality based on network performance."""
        if not self.adaptive or len(self.send_times) < 3:
            return

        avg_send_time = sum(self.send_times) / len(self.send_times)
        queue_size = self.frame_queue.qsize()
        queue_utilization = queue_size / self.max_queue_size

        # If sending is slow and queue is building up, reduce quality
        if avg_send_time > 0.5 and queue_utilization > 0.5:
            self.quality = max(50, self.quality - 5)
            logger.info(f"Reducing quality to {self.quality} (avg send time: {avg_send_time:.2f}s)")
        # If sending is fast and queue is empty, increase quality back to base
        elif avg_send_time < 0.2 and queue_utilization < 0.3 and self.quality < self.base_quality:
            self.quality = min(self.base_quality, self.quality + 5)
            logger.info(f"Increasing quality to {self.quality}")

    def _worker_loop(self):
        """Main worker loop for sending frames with adaptive control."""
        logger.info(f"Publisher worker started for {self.stream_name}")
        last_frame_time = 0
        frames_since_adapt = 0

        while not self.stop_event.is_set():
            try:
                # Get frame from queue with timeout
                frame = self.frame_queue.get(timeout=1)

                # Adaptive quality control every 30 frames
                if self.adaptive:
                    frames_since_adapt += 1
                    if frames_since_adapt >= 30:
                        self._adapt_quality()
                        frames_since_adapt = 0

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
                    # Don't wait on failure if queue is backing up
                    if self.frame_queue.qsize() < self.max_queue_size * 0.5:
                        time.sleep(min(1, self.retry_delay))

            except queue.Empty:
                # No frames in queue, continue waiting
                # Reset quality to base when idle
                if self.adaptive and self.quality < self.base_quality:
                    self.quality = self.base_quality
                continue
            except Exception as e:
                logger.error(f"Error in publisher worker: {e}", exc_info=True)
                time.sleep(self.retry_delay)

        logger.info(f"Publisher worker stopped - Total: {self.total_frames}, "
                   f"Failed: {self.failed_frames}, Dropped: {self.dropped_frames}, "
                   f"Skipped: {self.skipped_frames}")

    def get_stats(self) -> dict:
        """
        Get publisher statistics.

        Returns:
            Dictionary with statistics
        """
        avg_send_time = sum(self.send_times) / len(self.send_times) if self.send_times else 0
        queue_utilization = (self.frame_queue.qsize() / self.max_queue_size) * 100

        return {
            'stream_name': self.stream_name,
            'total_frames': self.total_frames,
            'failed_frames': self.failed_frames,
            'dropped_frames': self.dropped_frames,
            'skipped_frames': self.skipped_frames,
            'queue_size': self.frame_queue.qsize(),
            'queue_max': self.max_queue_size,
            'queue_utilization_pct': round(queue_utilization, 1),
            'current_quality': self.quality,
            'base_quality': self.base_quality,
            'avg_send_time_ms': round(avg_send_time * 1000, 1),
            'is_running': self.worker_thread and self.worker_thread.is_alive()
        }
