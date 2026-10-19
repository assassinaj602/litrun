#!/usr/bin/env bash
# litrun Release Packaging & Asset Bundler
set -euo pipefail

VERSION=${1:-"0.1.0"}
DIST_DIR="dist/releases/v${VERSION}"
mkdir -p "$DIST_DIR"

echo "==> Building native x86_64 core..."
make -C core clean all
cp core/bin/litrun-probe "$DIST_DIR/litrun-probe-x86_64"
cp core/lib/liblitrun_core.so "$DIST_DIR/liblitrun_core-x86_64.so"

echo "==> Cross-compiling ARM64 targets (if toolchain present)..."
if command -v aarch64-linux-gnu-gcc >/dev/null 2>&1; then
    ./scripts/cross_compile_arm64.sh all
    if [ -f "dist/binaries/arm64-a76-dotprod/litrun-probe" ]; then
        cp dist/binaries/arm64-a76-dotprod/litrun-probe "$DIST_DIR/litrun-probe-arm64-a76"
        cp dist/binaries/arm64-a76-dotprod/liblitrun_core.so "$DIST_DIR/liblitrun_core-arm64-a76.so"
    fi
    if [ -f "dist/binaries/arm64-a72-neon/litrun-probe" ]; then
        cp dist/binaries/arm64-a72-neon/litrun-probe "$DIST_DIR/litrun-probe-arm64-a72"
        cp dist/binaries/arm64-a72-neon/liblitrun_core.so "$DIST_DIR/liblitrun_core-arm64-a72.so"
    fi
    cp dist/binaries/*.tar.gz "$DIST_DIR/" 2>/dev/null || true
fi

echo "==> Calculating SHA-256 checksums..."
cd "$DIST_DIR"
sha256sum * > SHA256SUMS.txt 2>/dev/null || true
cd - >/dev/null

echo "✓ Release assets generated in $DIST_DIR:"
ls -lh "$DIST_DIR"

