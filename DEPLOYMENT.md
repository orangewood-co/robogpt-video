# Deployment Guide - RoboGPT Video Streaming System

This guide covers deploying the video streaming system to a production server with Traefik reverse proxy and automatic SSL certificates.

## Prerequisites

- Ubuntu/Debian server with Docker and Docker Compose installed
- Domain name pointed to server IP: `video.robogpt.infra.orangewood.co`
- Ports 80 and 443 open in firewall
- Root or sudo access

## Quick Deployment Steps

### 1. Install Docker and Docker Compose (if not already installed)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Add your user to docker group (optional)
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
docker compose version
```

### 2. Clone/Upload Project to Server

```bash
# Option A: Clone from Git
git clone <your-repo-url> /opt/robogpt-video
cd /opt/robogpt-video

# Option B: Upload files via SCP
scp -r /path/to/robogpt-video user@server:/opt/robogpt-video
ssh user@server
cd /opt/robogpt-video
```

### 3. Create Required Directories and Set Permissions

```bash
# Create Traefik directories
mkdir -p traefik/letsencrypt traefik/logs

# Create app directories
mkdir -p recordings logs

# Set permissions for Let's Encrypt certificate storage
touch traefik/letsencrypt/acme.json
chmod 600 traefik/letsencrypt/acme.json

# Set ownership (if running as non-root user)
sudo chown -R $USER:$USER /opt/robogpt-video
```

### 4. Configure Environment (Optional)

Edit `config.yaml` if you need custom settings:

```bash
nano config.yaml
```

Key settings to review:
- `streams.max_concurrent`: Adjust based on server resources
- `recording.retention_days`: Storage retention policy
- `server.port`: Keep as 5000 (internal)

### 5. Verify Docker Compose Configuration

Check that your domain is correctly set in `docker-compose.yml`:

```bash
grep "video.robogpt.infra.orangewood.co" docker-compose.yml
```

Should show:
```
- "traefik.http.routers.video-server.rule=Host(`video.robogpt.infra.orangewood.co`)"
```

### 6. Start Services

```bash
# Build and start in detached mode
docker compose up -d --build

# Check logs
docker compose logs -f

# Or check individual service logs
docker compose logs -f traefik
docker compose logs -f video-server
```

### 7. Verify Deployment

```bash
# Check running containers
docker compose ps

# Check Traefik is getting certificates
docker compose logs traefik | grep -i certificate

# Test health endpoint (after a minute for SSL to provision)
curl https://video.robogpt.infra.orangewood.co/health

# Test from browser
# Visit: https://video.robogpt.infra.orangewood.co/health
```

## Service URLs

After deployment, your services will be available at:

- **Video Server**: `https://video.robogpt.infra.orangewood.co`
- **Traefik Dashboard**: `https://traefik.robogpt.infra.orangewood.co` (username: `admin`, password: `change_me`)

### API Endpoints

- `POST https://video.robogpt.infra.orangewood.co/publish/<stream_name>`
- `GET https://video.robogpt.infra.orangewood.co/stream/<stream_name>`
- `GET https://video.robogpt.infra.orangewood.co/api/streams`
- `GET https://video.robogpt.infra.orangewood.co/health`

## Changing Traefik Dashboard Password

Generate a new password hash:

```bash
# Install apache2-utils if not present
sudo apt install apache2-utils -y

# Generate password hash (replace 'your_password' with your password)
echo $(htpasswd -nb admin your_password) | sed -e s/\\$/\\$\\$/g
```

Update the hash in `docker-compose.yml`:

```yaml
- "traefik.http.middlewares.dashboard-auth.basicauth.users=admin:$$apr1$$..."
```

Restart Traefik:

```bash
docker compose restart traefik
```

## Updating the Application

```bash
cd /opt/robogpt-video

# Pull latest code (if using Git)
git pull

# Rebuild and restart
docker compose down
docker compose up -d --build

# Or rolling update without downtime
docker compose build
docker compose up -d
```

## Monitoring and Maintenance

### View Logs

```bash
# All services
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100

# Specific service
docker compose logs -f video-server

# Application logs (inside container)
docker compose exec video-server tail -f /app/logs/server.log
```

### Check Resource Usage

```bash
# Container stats
docker stats

# Disk usage
df -h
du -sh /opt/robogpt-video/recordings/

# Check active streams
curl https://video.robogpt.infra.orangewood.co/api/streams
```

### Restart Services

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart video-server

# Stop all services
docker compose down

# Start all services
docker compose up -d
```

## Backup and Recovery

### Backup Recordings

```bash
# Create backup
tar -czf recordings-backup-$(date +%Y%m%d).tar.gz recordings/

# Copy to remote storage
scp recordings-backup-*.tar.gz user@backup-server:/backups/

# Or use rsync for incremental backups
rsync -avz recordings/ user@backup-server:/backups/robogpt-video/recordings/
```

### Backup Configuration

```bash
# Backup configuration files
tar -czf config-backup-$(date +%Y%m%d).tar.gz config.yaml docker-compose.yml

# Backup Traefik certificates (important!)
sudo tar -czf traefik-backup-$(date +%Y%m%d).tar.gz traefik/letsencrypt/acme.json
```

### Restore from Backup

```bash
# Stop services
docker compose down

# Restore recordings
tar -xzf recordings-backup-20260121.tar.gz

# Restore configuration
tar -xzf config-backup-20260121.tar.gz

# Restore certificates
sudo tar -xzf traefik-backup-20260121.tar.gz
sudo chmod 600 traefik/letsencrypt/acme.json

# Restart services
docker compose up -d
```

## Troubleshooting

### SSL Certificate Issues

```bash
# Check Traefik logs for certificate errors
docker compose logs traefik | grep -i error

# Verify DNS is pointing correctly
nslookup video.robogpt.infra.orangewood.co

# Check if ports 80 and 443 are accessible
sudo netstat -tulpn | grep -E ':(80|443)'

# If certificates fail, remove acme.json and restart
docker compose down
rm traefik/letsencrypt/acme.json
touch traefik/letsencrypt/acme.json
chmod 600 traefik/letsencrypt/acme.json
docker compose up -d
```

### Video Server Not Responding

```bash
# Check container status
docker compose ps

# Check logs
docker compose logs video-server

# Check if server is listening inside container
docker compose exec video-server netstat -tulpn | grep 5000

# Restart video server
docker compose restart video-server
```

### High Disk Usage

```bash
# Check disk space
df -h

# Find large files
du -sh recordings/* | sort -h

# Manual cleanup of old recordings (if auto-cleanup isn't working)
find recordings/ -type f -mtime +7 -delete

# Restart cleanup manager
docker compose restart video-server
```

### Container Won't Start

```bash
# Check detailed logs
docker compose logs video-server

# Check for port conflicts
sudo netstat -tulpn | grep 5000

# Remove containers and recreate
docker compose down
docker compose up -d --force-recreate
```

## Firewall Configuration

### UFW (Ubuntu)

```bash
# Allow SSH (important!)
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

### Firewalld (CentOS/RHEL)

```bash
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## Performance Tuning

### For High Traffic

Edit `config.yaml`:

```yaml
streams:
  max_concurrent: 100  # Increase based on server resources
  max_buffer_frames: 20  # Reduce to save memory

recording:
  enabled: true
  fps: 25  # Reduce if disk I/O is a bottleneck
```

### Docker Resource Limits

Add to `docker-compose.yml` under `video-server`:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 4G
    reservations:
      cpus: '1.0'
      memory: 2G
```

## System Service (Optional)

To auto-start on boot, create a systemd service:

```bash
sudo nano /etc/systemd/system/robogpt-video.service
```

```ini
[Unit]
Description=RoboGPT Video Streaming
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/robogpt-video
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable robogpt-video
sudo systemctl start robogpt-video
sudo systemctl status robogpt-video
```

## Security Hardening

### 1. Change Default Passwords

Update Traefik dashboard password (see above)

### 2. Restrict Traefik Dashboard Access (Optional)

Edit `docker-compose.yml` to remove dashboard labels if not needed:

```yaml
# Remove or comment out these lines:
# - "traefik.http.routers.dashboard.rule=Host(`traefik.robogpt.infra.orangewood.co`)"
# ... (all dashboard-related labels)
```

### 3. Enable Rate Limiting (Optional)

Add to Traefik labels in `docker-compose.yml`:

```yaml
- "traefik.http.middlewares.rate-limit.ratelimit.average=100"
- "traefik.http.middlewares.rate-limit.ratelimit.burst=50"
- "traefik.http.routers.video-server.middlewares=video-headers,rate-limit"
```

### 4. Configure Automated Backups

```bash
# Create backup script
sudo nano /usr/local/bin/backup-robogpt-video.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/backups/robogpt-video"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup recordings (only last 24 hours to save space)
find /opt/robogpt-video/recordings -type f -mtime -1 | tar -czf $BACKUP_DIR/recordings-$DATE.tar.gz -T -

# Backup config
tar -czf $BACKUP_DIR/config-$DATE.tar.gz -C /opt/robogpt-video config.yaml docker-compose.yml

# Cleanup old backups (keep last 7 days)
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup completed: $DATE"
```

```bash
# Make executable
sudo chmod +x /usr/local/bin/backup-robogpt-video.sh

# Add to crontab (daily at 2 AM)
sudo crontab -e
```

Add line:
```
0 2 * * * /usr/local/bin/backup-robogpt-video.sh >> /var/log/robogpt-backup.log 2>&1
```

## Testing After Deployment

### 1. Health Check

```bash
curl -k https://video.robogpt.infra.orangewood.co/health
```

Expected response:
```json
{
  "status": "healthy",
  "active_streams": 0,
  "max_streams": 50,
  "recording_enabled": true
}
```

### 2. Test Stream Publishing

```bash
# On your local machine with webcam
python client/examples/webcam_publisher.py \
  --server https://video.robogpt.infra.orangewood.co \
  --stream test_stream
```

### 3. View Stream

Open in browser:
```
https://video.robogpt.infra.orangewood.co/stream/test_stream
```

Or in HTML:
```html
<img src="https://video.robogpt.infra.orangewood.co/stream/test_stream">
```

## Support and Maintenance

### Regular Maintenance Tasks

**Daily:**
- Check disk space: `df -h`
- Monitor active streams: `curl https://video.robogpt.infra.orangewood.co/api/streams`

**Weekly:**
- Review logs: `docker compose logs --tail=1000`
- Check for Docker updates: `docker compose pull`
- Verify backups are running

**Monthly:**
- Review and cleanup old recordings manually if needed
- Update system packages: `sudo apt update && sudo apt upgrade`
- Review Traefik logs for security issues

### Useful Commands Reference

```bash
# Quick status check
docker compose ps && curl -s https://video.robogpt.infra.orangewood.co/health | jq

# View active streams
curl -s https://video.robogpt.infra.orangewood.co/api/streams | jq

# Follow all logs
docker compose logs -f --tail=50

# Restart everything
docker compose restart

# Complete rebuild
docker compose down && docker compose build --no-cache && docker compose up -d

# Clean up Docker system
docker system prune -a --volumes -f
```

## Production Checklist

- [ ] DNS A record for `video.robogpt.infra.orangewood.co` points to server IP
- [ ] Ports 80 and 443 open in firewall
- [ ] Docker and Docker Compose installed
- [ ] Project files uploaded to `/opt/robogpt-video`
- [ ] Traefik directories created with correct permissions
- [ ] `acme.json` created with 600 permissions
- [ ] `docker-compose.yml` configured with correct domain
- [ ] Traefik dashboard password changed
- [ ] Services started with `docker compose up -d`
- [ ] SSL certificates obtained (check Traefik logs)
- [ ] Health endpoint accessible via HTTPS
- [ ] Test stream publishing and viewing
- [ ] Backup scripts configured
- [ ] System service enabled (optional)
- [ ] Monitoring configured

## Contact

For issues or questions, refer to the main README.md or check the GitHub repository.
