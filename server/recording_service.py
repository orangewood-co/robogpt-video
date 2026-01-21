"""
Asynchronous video recording service.
"""
import os
import cv2
import json
import logging
import threading
import queue
import numpy as np
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path


logger = logging.getLogger(__name__)


class RecordingWorker:
    """Worker thread for recording a single stream."""

    def __init__(self, stream_name: str, base_dir: str, fps: int = 30, codec: str = 'mp4v'):
        """
        Initialize recording worker.

        Args:
            stream_name: Name of the stream
            base_dir: Base directory for recordings
            fps: Frames per second
            codec: Video codec
        """
        self.stream_name = stream_name
        self.base_dir = base_dir
        self.fps = fps
        self.codec = codec

        self.frame_queue = queue.Queue(maxsize=100)
        self.stop_event = threading.Event()
        self.thread = None

        self.video_writer: Optional[cv2.VideoWriter] = None
        self.recording_path: Optional[str] = None
        self.metadata_path: Optional[str] = None

        self.start_time: Optional[datetime] = None
        self.frame_count = 0
        self.is_recording = False

    def start(self):
        """Start the recording worker thread."""
        if self.thread and self.thread.is_alive():
            logger.warning(f"Recording worker for {self.stream_name} already running")
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info(f"Recording worker started for {self.stream_name}")

    def stop(self):
        """Stop the recording worker thread."""
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        self._cleanup_writer()
        logger.info(f"Recording worker stopped for {self.stream_name}")

    def add_frame(self, frame_data: bytes):
        """
        Add a frame to the recording queue.

        Args:
            frame_data: JPEG frame data
        """
        try:
            self.frame_queue.put(frame_data, block=False)
        except queue.Full:
            logger.warning(f"Recording queue full for {self.stream_name}, dropping frame")

    def _initialize_writer(self, frame_shape):
        """
        Initialize video writer.

        Args:
            frame_shape: Shape of the first frame (height, width, channels)
        """
        # Create stream directory
        stream_dir = os.path.join(self.base_dir, self.stream_name)
        os.makedirs(stream_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.stream_name}_{timestamp}.mp4"
        self.recording_path = os.path.join(stream_dir, filename)
        self.metadata_path = os.path.join(stream_dir, f"{self.stream_name}_{timestamp}.json")

        # Get codec
        fourcc = cv2.VideoWriter_fourcc(*self.codec)

        # Initialize VideoWriter
        height, width = frame_shape[:2]
        self.video_writer = cv2.VideoWriter(
            self.recording_path,
            fourcc,
            self.fps,
            (width, height)
        )

        if not self.video_writer.isOpened():
            logger.error(f"Failed to open video writer for {self.stream_name}")
            self.video_writer = None
            return False

        self.start_time = datetime.now()
        self.frame_count = 0
        self.is_recording = True

        logger.info(f"Recording started: {self.recording_path}")
        return True

    def _cleanup_writer(self):
        """Clean up video writer and save metadata."""
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None

        # Save metadata
        if self.is_recording and self.start_time:
            self._save_metadata()

        self.is_recording = False

    def _save_metadata(self):
        """Save recording metadata to JSON file."""
        if not self.metadata_path or not self.start_time:
            return

        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        avg_fps = self.frame_count / duration if duration > 0 else 0

        metadata = {
            'stream_name': self.stream_name,
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration,
            'total_frames': self.frame_count,
            'average_fps': round(avg_fps, 2),
            'target_fps': self.fps,
            'codec': self.codec,
            'recording_path': self.recording_path
        }

        try:
            with open(self.metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            logger.info(f"Metadata saved: {self.metadata_path}")
        except Exception as e:
            logger.error(f"Failed to save metadata: {e}")

    def _run(self):
        """Main worker loop."""
        logger.info(f"Recording worker running for {self.stream_name}")

        while not self.stop_event.is_set():
            try:
                # Get frame from queue with timeout
                frame_data = self.frame_queue.get(timeout=1)

                # Decode JPEG frame
                nparr = np.frombuffer(frame_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                if frame is None:
                    logger.warning(f"Failed to decode frame for {self.stream_name}")
                    continue

                # Initialize writer on first frame
                if not self.is_recording:
                    if not self._initialize_writer(frame.shape):
                        logger.error(f"Failed to initialize writer for {self.stream_name}")
                        break

                # Write frame
                if self.video_writer:
                    self.video_writer.write(frame)
                    self.frame_count += 1

            except queue.Empty:
                # No frames in queue, continue waiting
                continue
            except Exception as e:
                logger.error(f"Error in recording worker for {self.stream_name}: {e}", exc_info=True)
                break

        # Cleanup on exit
        self._cleanup_writer()
        logger.info(f"Recording worker finished for {self.stream_name}")


class RecordingService:
    """
    Service for managing multiple recording workers.
    """

    def __init__(self, base_dir: str = 'recordings', fps: int = 30, codec: str = 'mp4v'):
        """
        Initialize recording service.

        Args:
            base_dir: Base directory for recordings
            fps: Frames per second
            codec: Video codec
        """
        self.base_dir = base_dir
        self.fps = fps
        self.codec = codec

        self.workers: Dict[str, RecordingWorker] = {}
        self.lock = threading.Lock()

        # Create base directory
        os.makedirs(base_dir, exist_ok=True)

        logger.info(f"RecordingService initialized (base_dir={base_dir}, fps={fps}, codec={codec})")

    def start_recording(self, stream_name: str):
        """
        Start recording a stream.

        Args:
            stream_name: Name of the stream
        """
        with self.lock:
            if stream_name in self.workers:
                logger.debug(f"Recording already active for {stream_name}")
                return

            worker = RecordingWorker(
                stream_name=stream_name,
                base_dir=self.base_dir,
                fps=self.fps,
                codec=self.codec
            )
            worker.start()
            self.workers[stream_name] = worker

            logger.info(f"Recording started for stream: {stream_name}")

    def stop_recording(self, stream_name: str):
        """
        Stop recording a stream.

        Args:
            stream_name: Name of the stream
        """
        with self.lock:
            if stream_name not in self.workers:
                logger.debug(f"No active recording for {stream_name}")
                return

            worker = self.workers[stream_name]
            worker.stop()
            del self.workers[stream_name]

            logger.info(f"Recording stopped for stream: {stream_name}")

    def add_frame(self, stream_name: str, frame_data: bytes):
        """
        Add a frame to a stream's recording queue.

        Args:
            stream_name: Name of the stream
            frame_data: JPEG frame data
        """
        with self.lock:
            if stream_name not in self.workers:
                logger.debug(f"No active recording for {stream_name}, ignoring frame")
                return

            worker = self.workers[stream_name]

        # Add frame outside of lock to avoid blocking
        worker.add_frame(frame_data)

    def stop_all(self):
        """Stop all recording workers."""
        with self.lock:
            stream_names = list(self.workers.keys())

        for stream_name in stream_names:
            self.stop_recording(stream_name)

        logger.info("All recordings stopped")

    def get_active_recordings(self) -> list:
        """
        Get list of active recording stream names.

        Returns:
            List of stream names
        """
        with self.lock:
            return list(self.workers.keys())
