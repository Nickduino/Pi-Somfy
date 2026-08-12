#!/bin/bash
# build.sh — Local build helper (optional)
#
# The Dockerfile clones Pi-Somfy from GitHub at build time using the
# BUILD_VERSION arg, so no file copying is required.
# This script is only useful for building the add-on locally outside
# of Home Assistant Supervisor.
#
# Usage:  cd "somfy-ha-addon" && bash build.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Building Pi-Somfy add-on locally..."
docker build \
    --build-arg BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest \
    --build-arg BUILD_VERSION=3.0.0 \
    -t local/pi_somfy:3.0.0 \
    "${SCRIPT_DIR}"

echo "Done. Run with:  docker run --rm -it local/pi_somfy:3.0.0"
