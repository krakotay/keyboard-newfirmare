# Measured startup result

The device is a wired-only VGN V108. Stock and the earlier v1 reset-pulse
experiment both produced 13 EPROTO completions on each interrupt IN endpoint,
followed by two kernel recovery resets and successful keyboard traffic.

The user installed v2 and the saved independent 65536-byte readback matched the
published patched image exactly. Its last 4096 bytes matched the original
bootloader, including a separate bootloader read. The summarized write/readback
record is [firmware-verification.json](../reports/firmware-verification.json).

| Same physical port `3-2` | Stock | v1 | v2 |
|---|---:|---:|---:|
| EPROTO interrupt completions after reconnect | 26 | 26 | 0 |
| Kernel recovery resets | 2 | 2 | 0 |
| Successful 8-byte keyboard reports | 24 | 16 | 28 |
| Observation after new-address discovery, seconds | 8.699 | 7.029 | 7.971 |
| First submission to first keyboard report, ms; input-dependent | 4729.365 | 3496.832 | 2219.428 |

All three comparison captures were stopped with Ctrl+C. Each preserved the
reconnect and successful input traffic; the v2 trace includes the interval where
stock and v1 failed. Its address changed from 42 to 43. There were no interrupt
errors at address 43. One EPROTO completion at the old address 42 occurred during
the deliberate unplug and is excluded from the new-startup measurement.

Three control STALLs for GET_DESCRIPTOR value `0x0600` occur in all three captures.
They are separate from the interrupt EPROTO/recovery-reset pattern that
disappeared. The maximum v2 control transfer latency was 3.458 ms. Endpoint 2 was
submitted but had no completed input report in that capture, so media/NKRO
functionality is not established by it.

The prior EP0-localization experiment used periodic standard descriptor and
configuration reads on v1. Configuration 1 and a valid descriptor succeeded, then
20 probe requests returned EPROTO during the interrupt failure interval. It
recorded two recovery resets and later recovered, before the user's first input
after a ten-second wait. This supports a failure of USB as a whole. Probe traffic
changes scheduling; its 24 interrupt errors are not a performance comparison
with the passive 26-error baseline.

The kernel function trace identifies recovery through
`usb_reset_device <- __usb_queue_reset_device` in a worker. It does not show a
userspace application directly issuing those resets.

## What this establishes

One verified v2 reconnect no longer exhibits the measured startup fault, and the
user reports a clearly shorter delay. This supports the proposed deferred-reset
cause. No executing-PC trace proves that exact path in the failing original run.

The first-key timing is input-dependent and is not an exact readiness measurement
or evidence of a percentage speedup. There is only one passive comparison capture
per image. BIOS, repeated cold starts, suspend/resume, media/NKRO and post-v2
profile/keymap equality remain untested.

Run at least three ordinary reconnect captures with the same direct port and
cable, then test BIOS separately. No additional flash is required. Raw measured
evidence and portable English reports are indexed in [reports](../reports/README.md).
