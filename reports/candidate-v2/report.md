# VGN V108 USB startup report

- UTC: 20261018T053203.631255Z
- Label (user supplied): candidate-v2
- Verdict: **No interrupt transfer errors observed in this capture**
- Capture stop reason: user_interrupt
- Partial capture: True
- Physical reconnect observed: True
- USB bus / addresses: 3 / [43]
- Interrupt EPROTO (-71) completions: 0
- Kernel recovery resets: 0
- Maximum control transfer latency: 3.458 ms
- First USB submission to first 8-byte keyboard report: 2219.428 ms

- Standard control probe: {'enabled': False}
## Interrupt endpoints

| Endpoint | Successful | EPROTO | Other errors |
|---|---:|---:|---:|
| 1 | 28 | 0 | 0 |

## Comparison

Baseline: stock
EPROTO: 26 -> 0
Kernel resets: 2 -> 0

## Limits

- USB address change confirms re-enumeration, not a measured power-off interval.
- The first successful keyboard report depends on a key press and is not an exact readiness time.
- Time before USB enumeration and BIOS behavior are not measured.
- No keystroke payload is retained. The image label is user-supplied; firmware is not read or written.
