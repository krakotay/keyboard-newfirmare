# VGN V108 USB startup report

- UTC: 20261018T050500.973799Z
- Label (user supplied): stock
- Verdict: **Transport errors observed**
- Capture stop reason: user_interrupt
- Partial capture: True
- Physical reconnect observed: True
- USB bus / addresses: 3 / [32]
- Interrupt EPROTO (-71) completions: 26
- Kernel recovery resets: 2
- Maximum control transfer latency: 4.026 ms
- First USB submission to first 8-byte keyboard report: 4729.365 ms

## Interrupt endpoints

| Endpoint | Successful | EPROTO | Other errors |
|---|---:|---:|---:|
| 1 | 24 | 13 | 0 |
| 2 | 0 | 13 | 0 |

## Limits

- USB address change confirms re-enumeration, not a measured power-off interval.
- The first successful keyboard report depends on a key press and is not an exact readiness time.
- Time before USB enumeration and BIOS behavior are not measured.
- No keystroke payload is retained. The image label is user-supplied; firmware is not read or written.
