#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit tracked files and reachable history offline; never opens USB."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BINS = {'firmware/stock-full-isp.bin', 'firmware/patched-v2-full-isp.bin'}
PDFS = {
    'docs/datasheets/SH68F90-CV2.0.pdf': 'b131890d75d0d584b5f22167fb8f787a3c9f51927d22dbff48354751cd085bfb',
    'docs/datasheets/SH68F90A-CV1.0.pdf': 'ab5e4f5141cf5bc063ff15ae0617ba7cb8a953043c25599e359a875cd72fda4c',
}
MODULES = {
    'tools/sinowealth-kb-tool': 'f568bd4b7b56c2fc4e5899e3d24ca6106a940b6e',
    'references/smk': '69373bbb633bd1159f4541f486ff7506563a38ec',
}
ALLOWED_TOP = {'.gitignore', '.gitattributes', '.gitmodules', 'README.md',
               'LICENSE', 'THIRD_PARTY_NOTICES.md'}
REPORT_DIRS = {'stock', 'candidate-v1', 'candidate-v2', 'ep0-localization'}
REPORT_FILES = {'README.md', 'comparison.json', 'firmware-verification.json', 'reset-origin-ftrace.txt'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def allowed(path):
    p = Path(path)
    if path in ALLOWED_TOP or path in MODULES or path in BINS or path in PDFS or path in {'firmware/SHA256SUMS', 'firmware/manifest.json'}:
        return True
    if p.suffix in {'.asm', '.hex', '.bin', '.pdf', '.js', '.zip', '.bundle'}:
        return False
    parts = p.parts
    if parts[0] == 'reports':
        return len(parts) == 2 and parts[1] in REPORT_FILES or len(parts) == 3 and parts[1] in REPORT_DIRS
    return parts[0] in {'tools', 'tests', 'docs'} and '.git' not in parts and '__pycache__' not in parts


def check_blob(path, data):
    assert allowed(path), 'Excluded path in Git: ' + path
    if path in PDFS:
        assert hashlib.sha256(data).hexdigest() == PDFS[path], 'Changed manufacturer PDF: ' + path
    elif path not in BINS:
        assert b'\x00' not in data, 'Unexpected binary content: ' + path
        private_prefix = b'/' + b'home' + b'/'
        assert private_prefix not in data, 'Private home path in tracked content: ' + path
        if path.endswith('usbmon-headers.txt'):
            assert b' = ' not in data, 'USB payload found in published headers: ' + path


def main():
    from v108_common import images, trace_metrics, reset_lines
    verified = images()
    entries = []
    for row in git('ls-files', '--stage', '-z').split(b'\x00'):
        if not row:
            continue
        meta, raw_path = row.split(b'\t', 1)
        mode, oid, stage = meta.decode().split()
        path = raw_path.decode()
        assert stage == '0', 'Unmerged path: ' + path
        if mode == '160000':
            assert MODULES.get(path) == oid, 'Unexpected submodule/revision: ' + path
        else:
            check_blob(path, git('cat-file', 'blob', oid))
        entries.append(path)
    assert {p for p in entries if p.endswith('.bin')} == BINS, 'Expected exactly two firmware binaries'
    assert {p for p in entries if p.endswith('.pdf')} == set(PDFS), 'Expected exactly two original PDFs'
    assert set(MODULES).issubset(entries), 'Missing pinned open-source submodule'
    objects = 0
    for line in git('rev-list', '--objects', '--all').decode().splitlines():
        oid, separator, path = line.partition(' ')
        if separator and git('cat-file', '-t', oid).strip() == b'blob':
            check_blob(path, git('cat-file', 'blob', oid))
            objects += 1
    commits = int(git('rev-list', '--all', '--count'))
    assert commits, 'No publication commit exists'
    # Retained observations must still agree with the raw measurement files.
    for directory in REPORT_DIRS:
        folder = ROOT/'reports'/directory
        report = json.loads((folder/'report.json').read_text())
        assert trace_metrics((folder/'usbmon-headers.txt').read_text().splitlines(),
                             report['metrics']['bus'], report['metrics']['addresses']) == report['metrics']
        assert len(reset_lines((folder/'kernel-usb.log').read_text(), report['port'])) == report['kernel_reset_count']
    comparison = json.loads((ROOT/'reports/comparison.json').read_text())
    for path, expected in comparison['source_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == expected, 'Evidence checksum mismatch: ' + path
    print(f'Publication audit passed: {len(entries)} tracked paths, {commits} commit(s), {objects} history blobs.')
    print('Exactly two firmware images, two unchanged PDFs and two pinned open-source submodules.')
    print('Image checks, measurement metrics, evidence hashes and history path/content checks passed.')


if __name__ == '__main__':
    main()
