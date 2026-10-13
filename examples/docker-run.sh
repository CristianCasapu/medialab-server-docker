#!/bin/bash
# medialab Server with plain "docker run". Adjust the paths and values, then: bash docker-run.sh
# The administrator password is read from a file (never put it on the command line: it would end up in
# the shell history and in "docker inspect").
set -euo pipefail

IMAGE="ghcr.io/cristiancasapu/medialab-server:latest"
CONFIG_DIR="${CONFIG_DIR:-/srv/medialab/config}"
CACHE_DIR="${CACHE_DIR:-/srv/medialab/cache}"
MEDIA_DIR="${MEDIA_DIR:-/srv/media}"
SECRETS_DIR="${SECRETS_DIR:-/srv/medialab/secrets}"   # admin_password, license_key (one value per file)

mkdir -p "${CONFIG_DIR}" "${CACHE_DIR}" "${SECRETS_DIR}"

docker run -d \
  --name medialab-server \
  --restart unless-stopped \
  -p 8096:8096 \
  -p 7359:7359/udp \
  -v "${CONFIG_DIR}:/config" \
  -v "${CACHE_DIR}:/cache" \
  -v "${MEDIA_DIR}:/media:ro" \
  -v "${SECRETS_DIR}:/run/secrets:ro" \
  -e PUID="$(id -u)" \
  -e PGID="$(id -g)" \
  -e TZ="Europe/Bucharest" \
  -e MLW_SERVER_NAME="Home media" \
  -e MLW_PUBLISHED_URL="https://media.example.org" \
  -e MLW_KNOWN_PROXIES="172.16.0.0/12" \
  -e MLW_ADMIN_USER="admin" \
  -e MLW_ADMIN_PASSWORD_FILE="/run/secrets/admin_password" \
  -e MLW_PLUGINS="jf-rosub" \
  "${IMAGE}"

# Intel / AMD GPU (VAAPI / QSV): add   --device /dev/dri:/dev/dri -e MLW_HW_ACCEL=qsv   (or vaapi)
# NVIDIA GPU (nvidia-container-toolkit): add   --gpus all -e MLW_HW_ACCEL=nvenc
