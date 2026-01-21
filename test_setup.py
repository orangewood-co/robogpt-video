#!/usr/bin/env python3
"""
Quick setup test script to verify installation.
"""
import sys
import os

def check_import(module_name):
    """Try to import a module."""
    try:
        __import__(module_name)
        print(f"✓ {module_name}")
        return True
    except ImportError as e:
        print(f"✗ {module_name}: {e}")
        return False

def main():
    """Test the setup."""
    print("=" * 60)
    print("RoboGPT Video Streaming System - Setup Test")
    print("=" * 60)
    print("\nChecking dependencies...")

    dependencies = [
        'flask',
        'flask_cors',
        'cv2',
        'numpy',
        'apscheduler',
        'requests',
        'yaml'
    ]

    all_ok = True
    for dep in dependencies:
        if not check_import(dep):
            all_ok = False

    print("\nChecking project structure...")
    required_dirs = ['server', 'client', 'recordings', 'logs']
    for directory in required_dirs:
        if os.path.isdir(directory):
            print(f"✓ {directory}/")
        else:
            print(f"✗ {directory}/ (missing)")
            all_ok = False

    required_files = [
        'config.yaml',
        'requirements.txt',
        'run_server.py',
        'server/config.py',
        'server/app.py',
        'server/stream_manager.py',
        'server/recording_service.py',
        'server/cleanup_manager.py',
        'client/publisher.py'
    ]

    for filepath in required_files:
        if os.path.isfile(filepath):
            print(f"✓ {filepath}")
        else:
            print(f"✗ {filepath} (missing)")
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("SUCCESS: All checks passed!")
        print("\nYou can now start the server with:")
        print("  python run_server.py")
        print("\nOr run the webcam example:")
        print("  python client/examples/webcam_publisher.py")
        return 0
    else:
        print("FAILURE: Some checks failed.")
        print("\nPlease run: pip install -r requirements.txt")
        return 1

if __name__ == '__main__':
    sys.exit(main())
