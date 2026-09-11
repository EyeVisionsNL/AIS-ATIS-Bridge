#!/usr/bin/env bash
set -euo pipefail
COMMIT=61c5c4061967752da6b491a924664d72184b38fa
if command -v rtl_airband >/dev/null 2>&1; then exit 0; fi
apt-get install -y git cmake make g++ pkg-config libusb-1.0-0-dev librtlsdr-dev libconfig++-dev libfftw3-dev
BUILD_DIR=$(mktemp -d /tmp/ais-atis-airband.XXXXXX)
trap 'rm -rf "$BUILD_DIR"' EXIT
git clone https://github.com/charlie-foxtrot/RTLSDR-Airband.git "$BUILD_DIR/source"
git -C "$BUILD_DIR/source" checkout --detach "$COMMIT"
cmake -S "$BUILD_DIR/source" -B "$BUILD_DIR/build" -DNFM=ON -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR/build" --parallel "$(nproc)"
install -m 0755 "$BUILD_DIR/build/src/rtl_airband" /usr/local/bin/rtl_airband
