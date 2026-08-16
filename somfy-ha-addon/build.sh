#!/bin/bash
# build.sh — Local build helper (optional)
#
# The Dockerfile clones Pi-Somfy from GitHub at build time using the
# BUILD_VERSION arg, so no file copying is required.
# This script is only useful for building the add-on locally outside
# of Home Assistant Supervisor.
#
# Usage:  cd "Home Assistant/addon/pi_somfy" && bash build.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Read from config.yaml rather than hardcoding, so this can't drift out of
# sync with the tag Supervisor actually builds against.
BUILD_VERSION="$(grep -m1 '^version:' "${SCRIPT_DIR}/config.yaml" | sed -E 's/version: *"?([^"]+)"?/\1/')"

echo "Building Pi-Somfy add-on locally (version ${BUILD_VERSION})..."
docker build \
    --build-arg BUILD_FROM=ghcr.io/home-assistant/aarch64-base:latest \
    --build-arg BUILD_VERSION="${BUILD_VERSION}" \
    -t "local/pi_somfy:${BUILD_VERSION}" \
    "${SCRIPT_DIR}"

echo "Done. Run with:  docker run --rm -it local/pi_somfy:${BUILD_VERSION}"
