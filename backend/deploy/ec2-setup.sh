#!/usr/bin/env bash
# One-time setup on Ubuntu 22.04 EC2 (AWS free tier).
# Run as ubuntu user: bash ec2-setup.sh YOUR_GITHUB_REPO_URL
set -euo pipefail

REPO_URL="${1:-}"
APP_DIR="/opt/scalptrack"
SERVICE_NAME="scalptrack"

if [[ -z "$REPO_URL" ]]; then
  echo "Usage: bash ec2-setup.sh https://github.com/Ashok-461999/cryptoApp.git"
  exit 1
fi

sudo apt-get update -y
sudo apt-get install -y python3.13 python3.13-venv python3.13-dev git nginx

sudo mkdir -p "$APP_DIR"
sudo chown -R ubuntu:ubuntu "$APP_DIR"

if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR/backend"
python3.13 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p data
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env — edit: nano $APP_DIR/backend/.env"
fi

sudo cp deploy/scalptrack.service /etc/systemd/system/${SERVICE_NAME}.service
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

# Nginx reverse proxy (port 80 -> 8000)
sudo tee /etc/nginx/sites-available/scalptrack >/dev/null <<'NGINX'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
}
NGINX
sudo ln -sf /etc/nginx/sites-available/scalptrack /etc/nginx/sites-enabled/scalptrack
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo ""
echo "Done. Check: curl http://localhost/health"
echo "Service: sudo systemctl status ${SERVICE_NAME}"
