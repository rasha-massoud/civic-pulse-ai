#!/usr/bin/env bash
# CivicPulse AI — EC2 single-instance bootstrap (native installs, no Docker)
#
# Run this on a fresh Ubuntu 22.04 EC2 instance (as user-data on launch,
# or manually over SSH). It installs Postgres, Redis, Python, and Node
# directly on the instance, pulls the repo, builds the backend/dashboard,
# and wires up two systemd services so both survive reboots and crashes.
#
# Prerequisites before running:
#   - Instance has an IAM role attached with S3 access to the media bucket
#   - A real .env file will need to be placed at $APP_DIR/backend/.env (see
#     .env.example at the repo root) — this script does NOT create it
#     for you, since it contains secrets.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/rasha-massoud/civic-pulse-ai.git}"
APP_DIR="${APP_DIR:-/opt/civicpulse}"
RUN_USER="${RUN_USER:-$USER}"

echo ">>> Updating apt and installing base packages (git, curl, build tools)"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg git build-essential

echo ">>> Installing PostgreSQL"
sudo apt-get install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

echo ">>> Installing Redis"
sudo apt-get install -y redis-server
sudo systemctl enable --now redis-server

echo ">>> Installing Python 3, pip, and venv support"
sudo apt-get install -y python3 python3-pip python3-venv

echo ">>> Installing Node.js and npm"
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

echo ">>> Cloning repository into ${APP_DIR}"
if [ ! -d "${APP_DIR}/.git" ]; then
  sudo mkdir -p "${APP_DIR}"
  sudo chown "${RUN_USER}":"${RUN_USER}" "${APP_DIR}"
  git clone "${REPO_URL}" "${APP_DIR}"
else
  git -C "${APP_DIR}" pull
fi

if [ ! -f "${APP_DIR}/backend/.env" ]; then
  echo ">>> WARNING: ${APP_DIR}/backend/.env not found."
  echo "    Copy .env.example to backend/.env and fill in real credentials before starting the services:"
  echo "      cp ${APP_DIR}/.env.example ${APP_DIR}/backend/.env"
  exit 1
fi

echo ">>> Creating Python virtualenv and installing backend dependencies"
cd "${APP_DIR}/backend"
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo ">>> Running database migrations"
.venv/bin/alembic upgrade head

echo ">>> Installing dashboard dependencies and building for production"
cd "${APP_DIR}/dashboard"
npm install
npm run build

echo ">>> Installing 'serve' to host the built dashboard as a static site"
sudo npm install -g serve

echo ">>> Writing systemd service for the FastAPI backend (civicpulse-backend)"
sudo tee /etc/systemd/system/civicpulse-backend.service > /dev/null <<EOF
[Unit]
Description=CivicPulse AI backend (FastAPI via uvicorn)
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${APP_DIR}/backend
ExecStart=${APP_DIR}/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo ">>> Writing systemd service for the dashboard static site (civicpulse-dashboard)"
sudo tee /etc/systemd/system/civicpulse-dashboard.service > /dev/null <<EOF
[Unit]
Description=CivicPulse AI dashboard (static build served via 'serve')
After=network.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${APP_DIR}/dashboard
ExecStart=$(command -v serve) -s dist -l 5173
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo ">>> Reloading systemd and enabling services to start on boot"
sudo systemctl daemon-reload
sudo systemctl enable --now civicpulse-backend
sudo systemctl enable --now civicpulse-dashboard

echo ">>> Done."
echo "    Backend API:  http://<instance-ip>:8000"
echo "    Dashboard:    http://<instance-ip>:5173"
echo "    Check status with: sudo systemctl status civicpulse-backend civicpulse-dashboard"
echo "    Check logs with:   sudo journalctl -u civicpulse-backend -f"
