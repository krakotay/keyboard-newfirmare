# VGN V108 wired keyboard: USB startup patch

Experimental patch and Linux utilities for a **wired-only VGN V108**, USB
`391d:2005`, reported device version `30.09`, with an SH68F90/SH68F90A-family
SINOWEALTH controller. The observed fault was several seconds without input
after connection, followed by normal operation.

The v2 patch changes **one three-byte instruction** so USB reset/init runs during
the bus-reset interrupt instead of being deferred to the main loop. A late reset
could otherwise clear an address already assigned by the host.

| Same-port reconnect measurement | Stock | Earlier v1 experiment | v2 |
|---|---:|---:|---:|
| Interrupt EPROTO failures | 26 | 26 | 0 |
| Kernel recovery resets | 2 | 2 | 0 |
| Successful keyboard reports | 24 | 16 | 28 |

This is **one captured reconnect per image**, not a verified BIOS fix or an exact
startup-latency benchmark. The first key-report timestamp depends on user input.
The user reports a shorter delay. Details and limitations:
[results](docs/RESULTS.md), [patch](docs/PATCH.md), [measurement evidence](reports/README.md).

## Contents and rights

- `firmware/`: exactly two full 64-KiB ISP images, original and patched v2.
- `tools/`: checking, English reports, reproducible patch generation and guarded flashing.
- `reports/`: curated measurements of the startup fault, recovery resets and patch effect.
- `docs/datasheets/`: two unchanged manufacturer PDFs with their original sources.
- Open-source dependencies are pinned Git submodules with their own licenses.

Our patch, utilities, tests and instructions are [MIT licensed](LICENSE).
**Rights to the firmware binaries remain with the manufacturer and original
rights holders; the binaries and manufacturer PDFs are not MIT licensed.**
See [third-party notices](THIRD_PARTY_NOTICES.md). Full disassembly, manufacturer
website copies, intermediate dumps and unrelated logs are excluded.

## Check startup and create an English report

Python 3 and Linux are required. Checking does not need Rust, the flash utility
or access to firmware. From the repository root:

```bash
sudo python3 tools/check_startup.py --label candidate-v2 --seconds 30 \
  --compare reports/stock/report.json
```

After **CAPTURE READY**, disconnect for at least three seconds, reconnect to the
same direct USB port, then press and release a harmless key after input works.
Let the capture finish; Ctrl+C also saves a marked partial capture. English
`report.md` / `report.json` and payload-free USB headers are saved under a new
ignored `reports/startup-*/` directory. Key codes and typed text are not retained.
Repeat for at least three separate reconnects; test BIOS independently.

The capture may load `usbmon`; mounted debugfs is required. `--port 3-2` can pin
the physical port. Labels do not verify the installed firmware. An optional
`--control-probe` adds standard IN-only descriptor/configuration reads to localize
EP0 failure; it changes traffic and should be analyzed separately.

Offline analysis of the included evidence needs no root or keyboard:

```bash
python3 tools/check_startup.py --trace reports/candidate-v2/usbmon-headers.txt \
  --journal reports/candidate-v2/kernel-usb.log --bus 3 --address 43 --port 3-2 \
  --label candidate-v2-offline --compare reports/stock/report.json
```

## Verify or reproduce the images offline

```bash
sha256sum -c firmware/SHA256SUMS
python3 tools/flash_v108.py --image candidate-v2
python3 tools/prepare_usb_reset_v2.py --output dumps/reproduced-v2-full-isp.bin
cmp firmware/patched-v2-full-isp.bin dumps/reproduced-v2-full-isp.bin
```

The flash command is a dry run unless `--execute` is present. It verifies the two
known images without opening USB and without requiring the compiled flash tool.

## Build the separate flash utility

Initialize the pinned dependency, install the Linux build prerequisites and use
an installed stable Rust toolchain (Rust 1.87 or later):

```bash
git submodule update --init tools/sinowealth-kb-tool
sudo apt install build-essential pkg-config libusb-1.0-0-dev usbutils
bash tools/build.sh
```

SMK is an optional open-source reference; initialize it separately with
`git submodule update --init references/smk` if needed. Avoid the upstream flash
utility's integration test suite on a connected device: it performs real writes
against fixtures for other keyboards. Our tests below are offline only.

## Flash v2 or restore stock

**Already installed v2 does not need reflashing to run startup checks.** These
images and geometry are specific to the captured keyboard revision. Writing
erases and reprograms the main 60 KiB. Failed USB ISP access may prevent software
recovery; a hardware recovery procedure has not been verified.

```bash
# Install the reviewed experimental v2 image
sudo python3 tools/flash_v108.py --image candidate-v2 --execute

# Restore the original main firmware
sudo python3 tools/flash_v108.py --image stock --execute
```

The script requires exactly one matching device, pins its physical port, enters
ISP, backs up all 64 KiB, verifies the original 4-KiB bootloader, and derives a
60-KiB main-only write payload locally. It independently reads back the full
image, checks exact equality and unchanged bootloader, then reboots. If already
installed, erase/write is skipped. A failed write attempts a verified rollback to
the known pre-write stock or v2 image. Unknown current images are refused.

An existing ISP device (`0603:1020`) with a verified original bootloader can be
explicitly restored with `--image stock --execute --recover`. This is limited to
stock recovery. Local backups, derived payloads and English operation reports go
to ignored `dumps/flash-*/` directories. Passwords are entered interactively and
are never saved by these tools.

The two published **full ISP images are not physical/JTAG images**. The upstream
ISP protocol virtualizes reset-vector metadata. Do not pass the full 64-KiB files
directly to a flash writer; use the wrapper's derived main-only payload.

## Validate the publication

```bash
python3 -m unittest discover -s tests -v
python3 tools/audit_publication.py
git diff --check
```

Tests cover payload boundaries, readback failure and rollback with a mocked USB
transaction, exact patch bytes, the changed return path and capture interruption.
The audit inspects tracked content and reachable Git history for excluded files,
unexpected binary images, private paths and the pinned open-source submodules.
It never accesses the keyboard.
