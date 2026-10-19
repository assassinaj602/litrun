#!/usr/bin/env bash
# litrun Release Packaging & Asset Bundler
set -euo pipefail

VERSION=${1:-"0.1.0"}
DIST_DIR="dist/releases/v${VERSION}"
mkdir -p "$DIST_DIR"

echo "==> Building litrun native core..."
make -C core clean all

echo "==> Packaging native artifacts..."
cp core/bin/litrun-probe "$DIST_DIR/litrun-probe-$(uname -m)"
cp core/lib/liblitrun_core.so "$DIST_DIR/liblitrun_core-$(uname -m).so"

echo "==> Calculating SHA-256 checksums..."
cd "$DIST_DIR"
sha256sum * > SHA256SUMS.txt
cd - >/dev/null

echo "✓ Release assets generated in $DIST_DIR:"
ls -lh "$DIST_DIR"
