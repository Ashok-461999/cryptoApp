#!/usr/bin/env bash
# Pull latest backend code and restart (runs on EC2).
set -euo pipefail

APP_DIR="/opt/scalptrack"
BRANCH="${DEPLOY_BRANCH:-main}"

cd "$APP_DIR"
git fetch origin "$BRANCH"
git reset --hard "origin/$BRANCH"

cd backend
source .venv/bin/activate
pip install -r requirements.txt -q

sudo systemctl restart scalptrack
sleep 2
curl -sf http://127.0.0.1:8000/health | head -c 200
echo ""
echo "Deploy OK — $(date -u +%Y-%m-%dT%H:%M:%SZ)"
