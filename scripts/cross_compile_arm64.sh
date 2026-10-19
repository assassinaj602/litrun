#!/usr/bin/env bash
# litrun Multi-SoC Cross-Compilation Tooling
# Compiles litrun C core and llama.cpp inference engine tuned per microarchitecture:
#   - Cortex-A76 (Raspberry Pi 5, Rockchip RK3588) with ARMv8.2-A + FP16 + DotProd
#   - Cortex-A72 (Raspberry Pi 4) with ARMv8-A + NEON
#   - Cortex-A53 (Raspberry Pi 3, Zero 2 W) generic baseline

set -euo pipefail

TARGET_ARCH=${1:-"all"}
OUTPUT_DIR="dist/binaries"
mkdir -p "$OUTPUT_DIR"

echo "=========================================================="
echo "⚡ litrun Cross-Compilation Engine Pipeline"
echo "=========================================================="

compile_a76_pi5() {
    echo "==> Building target: Cortex-A76 / BCM2712 / RK3588..."
    local TARGET_DIR="$OUTPUT_DIR/arm64-a76-dotprod"
    mkdir -p "$TARGET_DIR"

    if command -v aarch64-linux-gnu-gcc >/dev/null 2>&1; then
        CC="aarch64-linux-gnu-gcc"
        CFLAGS="-march=armv8.2-a+fp16+dotprod -O3 -fPIC -Wall -Wextra"
        $CC $CFLAGS -Icore/include core/tools/probe_main.c core/fingerprint/fingerprint.c core/governor/governor.c -o "$TARGET_DIR/litrun-probe"
        $CC $CFLAGS -shared -Icore/include core/fingerprint/fingerprint.c core/governor/governor.c -o "$TARGET_DIR/liblitrun_core.so"
        tar -czf "$OUTPUT_DIR/litrun-core-arm64-a76.tar.gz" -C "$TARGET_DIR" litrun-probe liblitrun_core.so
        echo "✓ Built litrun-probe and liblitrun_core.so for ARM64 Cortex-A76"
    else
        echo "! aarch64-linux-gnu-gcc not found on host. Use Docker or zig cc for cross-compilation."
    fi
}

compile_a72_pi4() {
    echo "==> Building target: Cortex-A72 / BCM2711..."
    local TARGET_DIR="$OUTPUT_DIR/arm64-a72-neon"
    mkdir -p "$TARGET_DIR"

    if command -v aarch64-linux-gnu-gcc >/dev/null 2>&1; then
        CC="aarch64-linux-gnu-gcc"
        CFLAGS="-march=armv8-a+simd -O3 -fPIC -Wall -Wextra"
        $CC $CFLAGS -Icore/include core/tools/probe_main.c core/fingerprint/fingerprint.c core/governor/governor.c -o "$TARGET_DIR/litrun-probe"
        $CC $CFLAGS -shared -Icore/include core/fingerprint/fingerprint.c core/governor/governor.c -o "$TARGET_DIR/liblitrun_core.so"
        tar -czf "$OUTPUT_DIR/litrun-core-arm64-a72.tar.gz" -C "$TARGET_DIR" litrun-probe liblitrun_core.so
        echo "✓ Built litrun-probe and liblitrun_core.so for ARM64 Cortex-A72"
    else
        echo "! aarch64-linux-gnu-gcc not found on host. Use Docker or zig cc for cross-compilation."
    fi
}

case "$TARGET_ARCH" in
    "a76"|"pi5")
        compile_a76_pi5
        ;;
    "a72"|"pi4")
        compile_a72_pi4
        ;;
    "all")
        compile_a76_pi5
        compile_a72_pi4
        ;;
    *)
        echo "Unknown target $TARGET_ARCH. Options: a76, a72, all"
        exit 1
        ;;
esac

echo "Cross-compilation script completed."

