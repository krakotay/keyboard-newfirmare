# Curated hardware evidence

Only measurements directly relevant to startup delay, endpoint failure and USB
reinitialization are published. Firmware operation/build logs, host inventories,
configuration/keymap dumps, failed empty captures and unrelated traces are omitted.

| Path | Measurement |
|---|---|
| `stock/` | Same-port stock reconnect: 26 interrupt EPROTO, two recovery resets |
| `candidate-v1/` | Failed first experiment: same 26 errors and two resets |
| `candidate-v2/` | First verified v2 reconnect: zero interrupt errors, zero resets, 28 keyboard reports |
| `ep0-localization/` | Standard GET probe on v1: EP0 fails during the global USB fault |
| `reset-origin-ftrace.txt` | Kernel call chains that queue and execute USB recovery resets |
| `firmware-verification.json` | Summary of user-executed v2 write and independent readback; no extra binary copies |
| `comparison.json` | Portable comparison metrics and hashes of the retained evidence |

The startup reports and USB headers retain timestamps, statuses, transfer sizes,
bus/address and physical-port identifiers. Interrupt payloads and typed text were
not retained. The host name is replaced by `HOST` and project paths are made
relative for publication. Accordingly, hashes refer to these publication copies,
not the private originals. Measurements are unchanged.

All three passive comparison captures are partial captures with successful input
after reconnect. Labels alone do not prove installed firmware; the v2 independent
readback was separately verified before cleanup. Exact readiness time, repeated
cold-start reliability and BIOS behavior remain unproven. See
[results](../docs/RESULTS.md) for interpretation and limitations.

New live reports are written to ignored `reports/startup-*/` directories. Review
them deliberately before adding further hardware evidence to the publication.
