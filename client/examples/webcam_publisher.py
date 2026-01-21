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
    parser.add_argument('--server', type=str, default='https://video.robogpt.infra.orangewood.co',
                       help='Server URL (default: https://video.robogpt.infra.orangewood.co)')
    parser.add_argument('--stream', type=str, default='webcam',
                       help='Stream name (default: webcam)')
    parser.add_argument('--camera', type=int, default=1,
                       help='Camera index (default: 1)')
    parser.add_argument('--quality', type=int, default=75,
                       help='JPEG quality 0-100 (default: 75)')
    parser.add_argument('--fps', type=int, default=15,
                       help='Max FPS (default: 15)')
    parser.add_argument('--width', type=int, default=640,
                       help='Frame width (default: 640)')
    parser.add_argument('--height', type=int, default=480,
                       help='Frame height (default: 480)')
    parser.add_argument('--show', action='store_true',
                       help='Show local preview window')
    parser.add_argument('--no-adaptive', action='store_true',
                       help='Disable adaptive quality and rate control')
    parser.add_argument('--queue-size', type=int, default=15,
                       help='Maximum frame queue size (default: 15)')

    args = parser.parse_args()

    # Initialize publisher with adaptive control
    publisher = StreamPublisher(
        server_url=args.server,
        stream_name=args.stream,
        quality=args.quality,
        max_fps=args.fps,
        adaptive=not args.no_adaptive,
        max_queue_size=args.queue_size
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
    print(f"Adaptive mode: {'Enabled' if not args.no_adaptive else 'Disabled'}")
    print(f"Target FPS: {args.fps}, Quality: {args.quality}, Queue size: {args.queue_size}")
    print("Press Ctrl+C to stop...")
    print()

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
                stats = publisher.get_stats()
                info_text = f"Sent: {stats['total_frames']} | Q: {stats['queue_size']}/{stats['queue_max']} | Qual: {stats['current_quality']}"
                cv2.putText(frame, info_text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                cv2.imshow(f'Webcam Publisher - {args.stream}', frame)

                # Check for 'q' key to quit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("\nQuitting...")
                    break

            # Print detailed stats every 50 frames
            if frame_count % 50 == 0:
                stats = publisher.get_stats()
                print(f"[{frame_count:5d}] Sent: {stats['total_frames']:4d} | "
                      f"Queue: {stats['queue_size']:2d}/{stats['queue_max']:2d} ({stats['queue_utilization_pct']:5.1f}%) | "
                      f"Quality: {stats['current_quality']:2d} | "
                      f"Dropped: {stats['dropped_frames']:3d} | "
                      f"Skipped: {stats['skipped_frames']:3d} | "
                      f"Send: {stats['avg_send_time_ms']:5.1f}ms")

    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        print("\nCleaning up...")
        cap.release()
        publisher.stop()
        cv2.destroyAllWindows()

        # Print final statistics
        stats = publisher.get_stats()
        print("\n" + "=" * 60)
        print("Final Statistics:")
        print("=" * 60)
        print(f"Total frames captured:  {frame_count}")
        print(f"Total frames sent:      {stats['total_frames']}")
        print(f"Failed frames:          {stats['failed_frames']}")
        print(f"Dropped frames:         {stats['dropped_frames']}")
        print(f"Skipped frames:         {stats['skipped_frames']}")
        print(f"Final quality:          {stats['current_quality']}")
        print(f"Avg send time:          {stats['avg_send_time_ms']:.1f}ms")

        success_rate = (stats['total_frames'] / frame_count * 100) if frame_count > 0 else 0
        print(f"Success rate:           {success_rate:.1f}%")
        print("=" * 60)

    print("\nDone!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
