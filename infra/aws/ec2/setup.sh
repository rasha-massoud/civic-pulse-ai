#!/usr/bin/env bash
# CivicPulse AI — EC2 single-instance bootstrap
#
# Run this on a fresh Ubuntu 22.04 EC2 instance (as user-data on launch,
# or manually over SSH). It installs Docker + Compose, pulls the repo,
# and brings the full stack up via the root docker-compose.yml.
#
# Prerequisites before running:
#   - Instance has an IAM role attached with S3 access to the media bucket
#   - A real .env file will need to be placed at $APP_DIR/.env (see
#     .env.example at the repo root) — this script does NOT create it
#     for you, since it contains secrets.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/rasha-massoud/civic-pulse-ai.git}"
APP_DIR="${APP_DIR:-/opt/civicpulse}"

echo ">>> Installing Docker and Docker Compose plugin"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg git
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker "$USER"

echo ">>> Cloning repository into ${APP_DIR}"
if [ ! -d "${APP_DIR}/.git" ]; then
  sudo mkdir -p "${APP_DIR}"
  sudo chown "$USER":"$USER" "${APP_DIR}"
  git clone "${REPO_URL}" "${APP_DIR}"
else
  git -C "${APP_DIR}" pull
fi

if [ ! -f "${APP_DIR}/.env" ]; then
  echo ">>> WARNING: ${APP_DIR}/.env not found."
  echo "    Copy .env.example to .env and fill in real credentials before starting the stack:"
  echo "      cp ${APP_DIR}/.env.example ${APP_DIR}/.env"
  exit 1
fi

echo ">>> Starting stack"
cd "${APP_DIR}"
sudo docker compose up --build -d

echo ">>> Done. Backend should be reachable on port 8000, dashboard on 5173."
