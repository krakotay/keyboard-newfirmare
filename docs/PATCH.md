# USB bus-reset interrupt patch v2

This is a targeted binary modification for the exact original image identified
below. It is not replacement firmware source code or a general SH68F90 patch.

| Offset in full ISP image | Original bytes | Patched bytes |
|---|---|---|
| `0x6881` | `12 E1 53` | `02 DF BA` |

The original instruction calls a routine that sets a deferred-reset flag. The
main loop later consumes that flag and executes USB software reset/init, which
clears the device address. If host enumeration has already assigned an address,
that later operation could invalidate it.

The patch jumps directly to the existing critical reset/init wrapper at `0xDFBA`
from the bus-reset interrupt. That wrapper masks interrupts around the existing
reset/init operation and returns to the USB IRQ epilogue at `0x83B9`. Remaining
dispatch of the old interrupt snapshot is skipped. No new code is injected.

Exactly three bytes change. The original reset vector, USB/HID descriptors and
final 4096-byte bootloader remain byte-identical. The earlier failed v1 attach
change is absent; v2 is based directly on stock.

| Full ISP image, 65536 bytes | SHA-256 |
|---|---|
| Original | `7b1b64d424aad7fe3f9397c2480e8bd12186bad0899dd4d88ee8e39ff4cd8a84` |
| Patched v2 | `97e1f51c616a61b400b079cb5cf3b6a8a0a63bed485a19fcd838e3fc2bb8f6be` |

The reproducible operation is:

```python
patched = bytearray(stock)
assert patched[0x6881:0x6884] == bytes.fromhex('12 e1 53')
patched[0x6881:0x6884] = bytes.fromhex('02 df ba')
```

`tools/prepare_usb_reset_v2.py` additionally verifies the full input and output
hashes and refuses to overwrite an existing output. The flasher derives the first
61440 bytes as a local ISP payload; the bootloader is never included in that
write. Full images are retained for identification, reproduction and verification.

The measured first hardware result supports the deferred-reset hypothesis:
26 interrupt EPROTO failures and two kernel recovery resets disappeared in the
first captured v2 reconnect. It does not prove the exact executing PC at the old
failure. Moving initialization into an interrupt changes timing; repeated cold
starts, BIOS and other operating modes remain to be tested. The small control-path
interpreter in the tests is not a full MCU or timing simulation.

This independently authored patch and its description are MIT licensed. The
underlying manufacturer firmware in either binary retains its original rights.
No full disassembly or reconstructed manufacturer source is included.
