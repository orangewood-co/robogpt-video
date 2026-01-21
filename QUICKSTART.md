# Quick Start Guide

## Local Development

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
python run_server.py

# 3. Stream from webcam (in another terminal)
python client/examples/webcam_publisher.py

# 4. View the stream
# Open in browser: http://localhost:5000/stream/webcam
# Or open viewer.html in browser
```

## Production Deployment with Traefik

For production deployment with SSL and domain setup, see **[DEPLOYMENT.md](DEPLOYMENT.md)**

### Quick Production Deploy

```bash
# On your server
cd /opt/robogpt-video

# Create required directories
mkdir -p traefik/letsencrypt traefik/logs recordings logs
touch traefik/letsencrypt/acme.json
chmod 600 traefik/letsencrypt/acme.json

# Start services
docker compose up -d --build

# Check status
docker compose ps
docker compose logs -f
```

### Access URLs

**Development:**
- Local Server: `http://localhost:5000`
- Health Check: `http://localhost:5000/health`
- Stream: `http://localhost:5000/stream/<name>`

**Production (after deployment):**
- Server: `https://video.robogpt.infra.orangewood.co`
- Health Check: `https://video.robogpt.infra.orangewood.co/health`
- Stream: `https://video.robogpt.infra.orangewood.co/stream/<name>`
- Traefik Dashboard: `https://traefik.robogpt.infra.orangewood.co`

## Client Usage

### Using the Webcam Publisher

```bash
# Local development
python client/examples/webcam_publisher.py --server http://localhost:5000 --stream webcam

# Production
python client/examples/webcam_publisher.py --server https://video.robogpt.infra.orangewood.co --stream camera1
```

### Using in Web Page

```html
<!-- Development -->
<img src="http://localhost:5000/stream/webcam" width="640" height="480">

<!-- Production -->
<img src="https://video.robogpt.infra.orangewood.co/stream/camera1" width="640" height="480">
```

### Custom Python Client

```python
from client.publisher import StreamPublisher
import cv2

publisher = StreamPublisher(
    server_url="https://video.robogpt.infra.orangewood.co",
    stream_name="my_camera",
    quality=85
)

publisher.start()

cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    if ret:
        publisher.publish_frame(frame)

publisher.stop()
cap.release()
```

## API Examples

### Publish Frame (cURL)

```bash
# Capture frame and publish
ffmpeg -i /dev/video0 -frames:v 1 -f image2 frame.jpg
curl -X POST -F "frame=@frame.jpg" https://video.robogpt.infra.orangewood.co/publish/camera1
```

### Get Stream List

```bash
curl https://video.robogpt.infra.orangewood.co/api/streams | jq
```

### Get Stream Stats

```bash
curl https://video.robogpt.infra.orangewood.co/api/streams/camera1/stats | jq
```

### Delete Stream

```bash
curl -X DELETE https://video.robogpt.infra.orangewood.co/api/streams/camera1
```

## Common Tasks

### View Logs

```bash
# Docker logs
docker compose logs -f video-server

# Application logs
tail -f logs/server.log
```

### Check Active Streams

```bash
curl -s https://video.robogpt.infra.orangewood.co/api/streams | jq '.streams[] | {name, total_frames, viewer_count}'
```

### Manual Cleanup

```bash
# Cleanup old recordings (older than 7 days)
find recordings/ -type f -mtime +7 -delete
```

### Restart Services

```bash
# Development
# Just restart run_server.py

# Production
docker compose restart
```

## Troubleshooting

### Stream not appearing?

1. Check publisher is running and sending frames
2. Verify server is accessible: `curl http://localhost:5000/health`
3. Check logs: `docker compose logs video-server`

### High memory usage?

Reduce buffer size in `config.yaml`:
```yaml
streams:
  max_buffer_frames: 15  # Default is 30
```

### Recording not working?

Check recording is enabled in `config.yaml`:
```yaml
recording:
  enabled: true
```

## Next Steps

- **Full Documentation**: See [README.md](README.md)
- **Production Deployment**: See [DEPLOYMENT.md](DEPLOYMENT.md)
- **Configuration Options**: See [config.yaml](config.yaml)

## Support

For detailed troubleshooting and advanced configuration, refer to the full documentation.
