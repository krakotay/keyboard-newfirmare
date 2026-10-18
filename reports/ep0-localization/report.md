# VGN V108 USB startup report

- UTC: 20261018T052049.513131Z
- Label (user supplied): candidate-v1-ep0-localization
- Verdict: **Transport errors observed**
- Capture stop reason: timer_expired
- Partial capture: False
- Physical reconnect observed: True
- USB bus / addresses: 3 / [38]
- Interrupt EPROTO (-71) completions: 24
- Kernel recovery resets: 2
- Maximum control transfer latency: 3.51 ms
- First USB submission to first 8-byte keyboard report: 10555.094 ms

- Standard control probe: {'enabled': True, 'requests': 1028, 'errno_counts': {'0': 1004, '19': 2, '32': 2, '71': 20}, 'error': None, 'configuration_values': [1], 'maximum_latency_ms': 168.058, 'limitation': 'Periodic standard IN requests perturb USB traffic; use to localize the fault, not to benchmark unchanged startup latency.'}
## Interrupt endpoints

| Endpoint | Successful | EPROTO | Other errors |
|---|---:|---:|---:|
| 1 | 177 | 12 | 0 |
| 2 | 0 | 12 | 0 |

## Limits

- USB address change confirms re-enumeration, not a measured power-off interval.
- The first successful keyboard report depends on a key press and is not an exact readiness time.
- Time before USB enumeration and BIOS behavior are not measured.
- No keystroke payload is retained. The image label is user-supplied; firmware is not read or written.
