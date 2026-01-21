"""
Flask application for video streaming system.
"""
import logging
import os
from flask import Flask, request, Response, jsonify
from flask_cors import CORS
from werkzeug.exceptions import BadRequest, NotFound

from config import config
from stream_manager import StreamManager


# Setup logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format=config.log_format
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Enable CORS if configured
if config.cors_enabled:
    CORS(app)
    logger.info("CORS enabled for all origins")

# Initialize stream manager
stream_manager = StreamManager(
    max_concurrent=config.max_concurrent_streams,
    max_buffer_frames=config.max_buffer_frames
)

# Will be initialized by run_server.py
recording_service = None
cleanup_manager = None


def set_recording_service(service):
    """Set the recording service instance."""
    global recording_service
    recording_service = service


def set_cleanup_manager(manager):
    """Set the cleanup manager instance."""
    global cleanup_manager
    cleanup_manager = manager


@app.route('/health', methods=['GET'])
def health_check():
    """
    Health check endpoint with system metrics.

    Returns:
        JSON response with health status and metrics
    """
    stats = {
        'status': 'healthy',
        'active_streams': stream_manager.get_stream_count(),
        'max_streams': config.max_concurrent_streams,
        'recording_enabled': config.recording_enabled,
        'config': {
            'timeout_seconds': config.stream_timeout,
            'max_buffer_frames': config.max_buffer_frames,
            'retention_days': config.retention_days
        }
    }

    return jsonify(stats), 200


@app.route('/publish/<stream_name>', methods=['POST'])
def publish_frame(stream_name):
    """
    Publish a frame to a stream.

    Args:
        stream_name: Name of the stream

    Returns:
        JSON response with status
    """
    try:
        # Check if frame data is provided
        if 'frame' not in request.files:
            raise BadRequest("No frame data provided. Use 'frame' field in multipart/form-data")

        frame_file = request.files['frame']
        frame_data = frame_file.read()

        # Validate frame size
        if len(frame_data) > config.max_frame_size_bytes:
            raise BadRequest(f"Frame size exceeds maximum ({config.max_frame_size_bytes} bytes)")

        if len(frame_data) == 0:
            raise BadRequest("Empty frame data")

        # Create stream if it doesn't exist
        if not stream_manager.stream_exists(stream_name):
            try:
                stream_manager.create_stream(stream_name)
                logger.info(f"Auto-created stream: {stream_name}")

                # Start recording if enabled
                if recording_service and config.recording_enabled:
                    recording_service.start_recording(stream_name)

            except ValueError as e:
                raise BadRequest(str(e))
            except RuntimeError as e:
                return jsonify({'error': str(e)}), 503

        # Publish the frame
        success = stream_manager.publish_frame(stream_name, frame_data)

        if not success:
            raise BadRequest("Failed to publish frame")

        # Add frame to recording queue
        if recording_service and config.recording_enabled:
            recording_service.add_frame(stream_name, frame_data)

        return jsonify({
            'status': 'success',
            'stream': stream_name,
            'frame_size': len(frame_data)
        }), 200

    except BadRequest as e:
        logger.warning(f"Bad request for stream {stream_name}: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error publishing frame to {stream_name}: {e}", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/stream/<stream_name>', methods=['GET'])
def stream_video(stream_name):
    """
    Stream video as MJPEG.

    Args:
        stream_name: Name of the stream

    Returns:
        MJPEG stream response
    """
    if not stream_manager.stream_exists(stream_name):
        raise NotFound(f"Stream '{stream_name}' not found")

    logger.info(f"New viewer connected to stream: {stream_name}")

    return Response(
        stream_manager.get_stream_generator(stream_name),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/api/streams', methods=['GET'])
def list_streams():
    """
    List all active streams.

    Returns:
        JSON response with list of streams
    """
    streams = stream_manager.get_all_streams_stats()

    return jsonify({
        'count': len(streams),
        'streams': streams
    }), 200


@app.route('/api/streams/<stream_name>/stats', methods=['GET'])
def stream_stats(stream_name):
    """
    Get statistics for a specific stream.

    Args:
        stream_name: Name of the stream

    Returns:
        JSON response with stream statistics
    """
    stats = stream_manager.get_stats(stream_name)

    if stats is None:
        raise NotFound(f"Stream '{stream_name}' not found")

    return jsonify(stats), 200


@app.route('/api/streams/<stream_name>', methods=['DELETE'])
def delete_stream(stream_name):
    """
    Manually delete a stream.

    Args:
        stream_name: Name of the stream

    Returns:
        JSON response with status
    """
    # Stop recording first
    if recording_service:
        recording_service.stop_recording(stream_name)

    # Delete the stream
    success = stream_manager.delete_stream(stream_name)

    if not success:
        raise NotFound(f"Stream '{stream_name}' not found")

    return jsonify({
        'status': 'success',
        'message': f"Stream '{stream_name}' deleted"
    }), 200


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({'error': str(error)}), 404


@app.errorhandler(400)
def bad_request(error):
    """Handle 400 errors."""
    return jsonify({'error': str(error)}), 400


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}", exc_info=True)
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # This should not be run directly in production
    # Use run_server.py instead
    logger.warning("Running Flask development server. Use run_server.py for production.")
    app.run(
        host=config.server_host,
        port=config.server_port,
        debug=config.server_debug
    )
