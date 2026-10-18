# SPDX-License-Identifier: MIT
"""Offline regression checks for publication image generation and dry run."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from v108_common import CheckError, images


class PublicationToolsTest(unittest.TestCase):
    def test_reproducer_matches_published_v2_and_rejects_modified_stock(self):
        from prepare_usb_reset_v2 import build_candidate
        known = images()
        self.assertEqual(build_candidate(known['stock']['full']), known['candidate-v2']['full'])
        corrupt = bytearray(known['stock']['full'])
        corrupt[100] ^= 1
        with self.assertRaises(CheckError):
            build_candidate(bytes(corrupt))

    def test_dry_run_needs_no_compiled_cli_and_never_discovers_usb(self):
        import flash_v108
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('stock', 'candidate-v2'):
                out = root/name
                argv = ['flash_v108.py', '--image', name, '--output', str(out)]
                with patch.object(flash_v108, 'ROOT', root), \
                     patch.object(flash_v108, 'images', return_value=images()), \
                     patch.object(flash_v108, 'target', side_effect=AssertionError('USB discovery forbidden')), \
                     patch.object(sys, 'argv', argv), contextlib.redirect_stdout(io.StringIO()):
                    flash_v108.main()
                report = json.loads((out/'report.json').read_text())
                self.assertEqual(report['status'], 'dry_run_passed_no_device_commands')
                self.assertFalse(any(out.glob('*.bin')))


if __name__ == '__main__':
    unittest.main()
