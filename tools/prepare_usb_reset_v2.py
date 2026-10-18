#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the v2 image offline from the exact stock image. Never opens USB."""
import argparse
from pathlib import Path
from v108_common import ROOT, STOCK_SHA, CANDIDATE_SHA, require, sha


def build_candidate(stock):
    require(len(stock) == 65536 and sha(stock) == STOCK_SHA, 'Stock image checksum/length mismatch')
    require(stock[0x6881:0x6884] == bytes.fromhex('12e153'), 'Unexpected original instruction')
    result = bytearray(stock)
    result[0x6881:0x6884] = bytes.fromhex('02dfba')
    result = bytes(result)
    require(sha(result) == CANDIDATE_SHA, 'Unexpected resulting image checksum')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', type=Path, default=ROOT/'firmware/stock-full-isp.bin')
    parser.add_argument('--output', type=Path, default=ROOT/'dumps/generated-v2-full-isp.bin')
    args = parser.parse_args()
    result = build_candidate(args.stock.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(result)
    print('Prepared full ISP image:', args.output)
    print('SHA-256:', sha(result))
    print('Use flash_v108.py to flash: this full image is NOT a physical/JTAG or direct write payload.')


if __name__ == '__main__':
    main()
