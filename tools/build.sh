#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
export CARGO_HOME="$project_dir/.cargo-home"
export CARGO_TARGET_DIR="$project_dir/build"
if [[ -f "$project_dir/.deps/usr/lib/x86_64-linux-gnu/pkgconfig/libusb-1.0.pc" ]]; then
  export PKG_CONFIG_PATH="$project_dir/.deps/usr/lib/x86_64-linux-gnu/pkgconfig"
  export PKG_CONFIG_SYSROOT_DIR="$project_dir/.deps"
else
  pkg-config --exists libusb-1.0 || {
    echo 'Install pkg-config and libusb-1.0-0-dev first; see README.md.' >&2
    exit 1
  }
fi
cargo +stable build --locked --release --manifest-path tools/sinowealth-kb-tool/Cargo.toml
mkdir -p bin
cp build/release/sinowealth-kb-tool bin/
