#!/usr/bin/env python3
"""
Example: Stream webcam to the video streaming server.
"""
import sys
import os
import cv2
import argparse
import signal

# Add parent directory to path to import publisher
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from publisher import StreamPublisher


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Stream webcam to video server')
    parser.add_argument('--server', type=str, default='http://localhost:5000',
                       help='Server URL (default: http://localhost:5000)')
    parser.add_argument('--stream', type=str, default='webcam',
                       help='Stream name (default: webcam)')
    parser.add_argument('--camera', type=int, default=0,
                       help='Camera index (default: 0)')
    parser.add_argument('--quality', type=int, default=85,
                       help='JPEG quality 0-100 (default: 85)')
    parser.add_argument('--fps', type=int, default=30,
                       help='Max FPS (default: 30)')
    parser.add_argument('--width', type=int, default=640,
                       help='Frame width (default: 640)')
    parser.add_argument('--height', type=int, default=480,
                       help='Frame height (default: 480)')
    parser.add_argument('--show', action='store_true',
                       help='Show local preview window')

    args = parser.parse_args()

    # Initialize publisher
    publisher = StreamPublisher(
        server_url=args.server,
        stream_name=args.stream,
        quality=args.quality,
        max_fps=args.fps
    )

    # Open webcam
    print(f"Opening camera {args.camera}...")
    cap = cv2.VideoCapture(args.camera)

    if not cap.isOpened():
        print(f"Error: Could not open camera {args.camera}")
        return 1

    # Set camera properties
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    cap.set(cv2.CAP_PROP_FPS, args.fps)

    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = int(cap.get(cv2.CAP_PROP_FPS))

    print(f"Camera opened: {actual_width}x{actual_height} @ {actual_fps} FPS")
    print(f"Streaming to: {args.server}/stream/{args.stream}")
    print("Press Ctrl+C to stop...")

    # Start publisher
    publisher.start()

    # Setup signal handler for graceful shutdown
    def signal_handler(sig, frame):
        print("\nStopping...")
        cap.release()
        publisher.stop()
        cv2.destroyAllWindows()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Main loop
    frame_count = 0
    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                print("Error: Failed to read frame from camera")
                break

            # Publish frame
            publisher.publish_frame(frame)
            frame_count += 1

            # Show local preview if requested
            if args.show:
                # Add info overlay
                info_text = f"Frame: {frame_count} | Queue: {publisher.frame_queue.qsize()}"
                cv2.putText(frame, info_text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                cv2.imshow(f'Webcam Publisher - {args.stream}', frame)

                # Check for 'q' key to quit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\nQuitting...")
                    break

            # Print stats every 100 frames
            if frame_count % 100 == 0:
                stats = publisher.get_stats()
                print(f"Stats - Sent: {stats['total_frames']}, "
                      f"Failed: {stats['failed_frames']}, "
                      f"Queue: {stats['queue_size']}")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        print("Cleaning up...")
        cap.release()
        publisher.stop()
        cv2.destroyAllWindows()

    print("Done!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
