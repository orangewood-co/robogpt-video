# RoboGPT Video Streaming System

A scalable HTTP-based video streaming system with dynamic endpoints, automatic recording, and intelligent cleanup.

## Features

- **Dynamic Streams**: Auto-create streams on first publish (`/publish/<name>` → `/stream/<name>`)
- **Concurrent Recording**: Automatic recording to disk with configurable retention
- **Smart Cleanup**: Auto-cleanup of inactive streams and old recordings
- **High Scalability**: Support for 50+ concurrent streams
- **No Authentication**: Public access for easy integration
- **MJPEG Streaming**: Browser-compatible video streaming
- **RESTful API**: Complete API for stream management

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd robogpt-video

# Install dependencies
pip install -r requirements.txt
```

### Start the Server

```bash
python run_server.py
```

The server will start on `http://localhost:5000`

### Stream from Webcam

```bash
# Basic usage
python client/examples/webcam_publisher.py

# Custom configuration
python client/examples/webcam_publisher.py \
  --server http://localhost:5000 \
  --stream my_camera \
  --camera 0 \
  --quality 85 \
  --fps 30
```

### View the Stream

Open in your browser:
```
http://localhost:5000/stream/webcam
```

Or create an HTML page:
```html
<!DOCTYPE html>
<html>
<body>
  <h1>My Stream</h1>
  <img src="http://localhost:5000/stream/webcam" width="640" height="480">
</body>
</html>
```

## Architecture

```
Client → POST /publish/<name> → StreamManager
                                      ↓
                            ┌─────────┴─────────┐
                            │                   │
                   RecordingService    GET /stream/<name>
                            │                   │
                            ↓                   ↓
                   recordings/*.mp4        MJPEG Stream

CleanupManager → Removes inactive streams & old files
```

## API Documentation

### Publish Frame

**POST** `/publish/<stream_name>`

Publish a JPEG frame to a stream. Creates stream automatically if it doesn't exist.

**Request:**
- Content-Type: `multipart/form-data`
- Field: `frame` (JPEG image file)

**Response:**
```json
{
  "status": "success",
  "stream": "camera1",
  "frame_size": 45678
}
```

### View Stream

**GET** `/stream/<stream_name>`

Get MJPEG video stream.

**Response:**
- Content-Type: `multipart/x-mixed-replace; boundary=frame`
- Body: MJPEG stream

### List Streams

**GET** `/api/streams`

List all active streams with statistics.

**Response:**
```json
{
  "count": 2,
  "streams": [
    {
      "name": "camera1",
      "created_at": "2026-01-21T10:30:00",
      "uptime_seconds": 923,
      "total_frames": 27690,
      "viewer_count": 3,
      "inactive_seconds": 0.5
    }
  ]
}
```

### Stream Statistics

**GET** `/api/streams/<stream_name>/stats`

Get detailed statistics for a specific stream.

**Response:**
```json
{
  "name": "camera1",
  "created_at": "2026-01-21T10:30:00",
  "uptime_seconds": 923,
  "last_frame_time": "2026-01-21T10:45:23",
  "inactive_seconds": 0.5,
  "total_frames": 27690,
  "viewer_count": 3,
  "buffer_size": 30,
  "has_current_frame": true
}
```

### Delete Stream

**DELETE** `/api/streams/<stream_name>`

Manually delete a stream and stop recording.

**Response:**
```json
{
  "status": "success",
  "message": "Stream 'camera1' deleted"
}
```

### Health Check

**GET** `/health`

Server health check and system metrics.

**Response:**
```json
{
  "status": "healthy",
  "active_streams": 5,
  "max_streams": 50,
  "recording_enabled": true,
  "config": {
    "timeout_seconds": 300,
    "max_buffer_frames": 30,
    "retention_days": 7
  }
}
```

## Configuration

Edit `config.yaml` to customize settings:

```yaml
streams:
  timeout_seconds: 300      # Inactivity timeout (5 minutes)
  max_concurrent: 50        # Maximum concurrent streams
  max_buffer_frames: 30     # Frame buffer size per stream

recording:
  enabled: true             # Enable/disable recording
  codec: mp4v               # Video codec (mp4v, h264)
  fps: 30                   # Recording FPS
  retention_days: 7         # Days to keep recordings

cleanup:
  interval_seconds: 60      # Cleanup check interval
  schedule_time: "03:00"    # Daily cleanup time (HH:MM)

server:
  host: 0.0.0.0            # Bind address
  port: 5000               # Server port
  debug: false             # Debug mode
  cors_enabled: true       # Enable CORS
  max_frame_size_mb: 10    # Max frame size

logging:
  level: INFO              # Log level
```

### Environment Variables

Override configuration via environment variables:

```bash
export STREAM_TIMEOUT_SECONDS=600
export MAX_CONCURRENT_STREAMS=100
export RECORDING_RETENTION_DAYS=14
export LOG_LEVEL=DEBUG
export SERVER_PORT=8080
export SERVER_DEBUG=true
```

## Client Usage

### Using the Generic Publisher

```python
from client.publisher import StreamPublisher
import cv2

# Initialize publisher
publisher = StreamPublisher(
    server_url="http://localhost:5000",
    stream_name="my_stream",
    quality=85,
    max_fps=30
)

# Start publisher thread
publisher.start()

# Capture and publish frames
cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    if ret:
        publisher.publish_frame(frame)

# Cleanup
publisher.stop()
cap.release()
```

### Custom Publisher

```python
import requests
import cv2

def publish_frame(stream_name, frame):
    # Encode frame to JPEG
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

    # Send to server
    files = {'frame': ('frame.jpg', buffer.tobytes(), 'image/jpeg')}
    response = requests.post(f'http://localhost:5000/publish/{stream_name}', files=files)

    return response.status_code == 200
```

## Recording Management

### Recording Structure

```
recordings/
  └── camera1/
      ├── camera1_20260121_103000.mp4
      ├── camera1_20260121_103000.json
      └── ...
```

### Metadata Format

Each recording has an accompanying JSON metadata file:

```json
{
  "stream_name": "camera1",
  "start_time": "2026-01-21T10:30:00Z",
  "end_time": "2026-01-21T10:45:23Z",
  "duration_seconds": 923,
  "total_frames": 27690,
  "average_fps": 30.0,
  "target_fps": 30,
  "codec": "mp4v",
  "recording_path": "recordings/camera1/camera1_20260121_103000.mp4"
}
```

## Resource Management

### Memory Usage

- Per-stream: ~6MB (30 frames × 200KB average)
- 50 streams: ~300MB
- Total system: ~400MB baseline

### Disk Usage

- ~6MB/min per stream recording
- ~360MB/hour per stream
- Automatic cleanup after retention period

### CPU Usage

- Minimal server load (no transcoding)
- ~5-10% CPU per active stream
- JPEG compression done client-side

## Cleanup Behavior

### Inactive Stream Cleanup

- Runs every 60 seconds (configurable)
- Removes streams with no frames for 5+ minutes
- Stops recording gracefully
- Logs all cleanup actions

### Old Recording Cleanup

- Runs daily at 3:00 AM (configurable)
- Deletes recordings older than 7 days (configurable)
- Removes empty directories
- Logs all deletions with file sizes

## Production Deployment

### Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create directories
RUN mkdir -p recordings logs

# Expose port
EXPOSE 5000

# Run server
CMD ["python", "run_server.py"]
```

Build and run:

```bash
docker build -t robogpt-video .
docker run -p 5000:5000 -v ./recordings:/app/recordings robogpt-video
```

### Systemd Service

Create `/etc/systemd/system/robogpt-video.service`:

```ini
[Unit]
Description=RoboGPT Video Streaming Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/robogpt-video
ExecStart=/usr/bin/python3 /opt/robogpt-video/run_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable robogpt-video
sudo systemctl start robogpt-video
```

## Security Considerations

- **Stream Names**: Validated to alphanumeric + underscore/dash only
- **Frame Size Limits**: Default 10MB max per frame
- **Resource Limits**: Max 50 concurrent streams (configurable)
- **File System Safety**: Path traversal prevention
- **CORS**: Configurable cross-origin access

### Production Recommendations

1. Use a reverse proxy (nginx) for SSL/TLS
2. Implement rate limiting per IP
3. Add authentication for sensitive streams
4. Monitor disk usage and set alerts
5. Regular backup of recordings
6. Use dedicated storage for recordings

## Troubleshooting

### Stream not appearing

1. Check server logs: `tail -f logs/server.log`
2. Verify stream was created: `curl http://localhost:5000/api/streams`
3. Check publisher is running and sending frames
4. Verify network connectivity

### Recording not working

1. Check recording is enabled in config.yaml
2. Verify recordings directory is writable
3. Check disk space: `df -h`
4. Review server logs for errors

### High memory usage

1. Reduce `max_buffer_frames` in config
2. Lower `max_concurrent` streams limit
3. Check for stuck streams with `GET /api/streams`
4. Reduce frame size or quality on client side

### Performance issues

1. Monitor CPU usage: `top` or `htop`
2. Check network bandwidth
3. Reduce FPS on clients
4. Lower JPEG quality
5. Consider horizontal scaling

## Development

### Running Tests

```bash
# Install dev dependencies
pip install pytest pytest-cov

# Run tests
pytest tests/

# With coverage
pytest --cov=server tests/
```

### Project Structure

```
robogpt-video/
├── server/
│   ├── app.py                 # Flask application
│   ├── config.py              # Configuration management
│   ├── stream_manager.py      # Stream management
│   ├── recording_service.py   # Video recording
│   └── cleanup_manager.py     # Background cleanup
├── client/
│   ├── publisher.py           # Generic publisher
│   └── examples/
│       └── webcam_publisher.py
├── recordings/                # Video storage
├── logs/                      # Application logs
├── config.yaml                # Configuration
├── requirements.txt           # Dependencies
├── run_server.py             # Server startup
└── README.md                 # Documentation
```

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## Support

For issues and questions:
- Create an issue on GitHub
- Check existing issues for solutions
- Review server logs for error details
