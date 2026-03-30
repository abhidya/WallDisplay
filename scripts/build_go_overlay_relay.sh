#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_BIN="${1:-$ROOT_DIR/bin/go_overlay_relay}"
HOST_OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
HOST_ARCH="$(uname -m)"

case "$HOST_OS" in
  darwin) GOOS="darwin" ;;
  linux) GOOS="linux" ;;
  *) echo "unsupported host OS: $HOST_OS" >&2; exit 1 ;;
esac

case "$HOST_ARCH" in
  arm64|aarch64) GOARCH="arm64" ;;
  x86_64|amd64) GOARCH="amd64" ;;
  *) echo "unsupported host arch: $HOST_ARCH" >&2; exit 1 ;;
esac

mkdir -p "$(dirname "$OUT_BIN")"

docker run --rm \
  -v "$ROOT_DIR:/src" \
  -w /src/tools/go_overlay_relay \
  golang:1.22 \
  /bin/bash -lc "CGO_ENABLED=0 GOOS=$GOOS GOARCH=$GOARCH go build -o /src/${OUT_BIN#"$ROOT_DIR"/} ."

echo "built $OUT_BIN"
