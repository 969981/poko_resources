"""Regression tests for native Pokopia text export (synthetic M7 binary fixtures)."""
import csv
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts' / 'resources'))
from export_native_text_files import LANGS, run


def source(values, forms=1):
    width = 8 if forms == 1 else 32
    n = len(values)
    b = bytearray(64 + n * width)
    struct.pack_into('<II', b, 0, n, 0)
    for row, value in enumerate(values):
        for form, text in enumerate([value] if forms == 1 else value):
            ptr = 64 + row * width + form * 4
            struct.pack_into('<I', b, ptr, len(b) - ptr)
            b.extend(text.encode('utf-8') + b'\0')
        if forms == 1:
            struct.pack_into('<I', b, 64 + row * width + 4, 0x1234)
        else:
            struct.pack_into('<II', b, 64 + row * width + 24, 0xab, 0xcd)
    return bytes(b)


def fixture(root, forms=1):
    decoded = root / 'decoded'
    decoded.mkdir()
    inventory, groups = root / 'inventory.csv', root / 'groups.csv'
    values = (['Line one\\literal\nwith newline', ''] if forms == 1 else [
        ['First', 'One\tTwo', '三', '', 'x', '🎮'], ['', '', '', '', '', '']])
    with inventory.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['entry', 'sha256', 'status'])
        w.writeheader()
        for index in range(9):
            b = source(values, forms)
            (decoded / f'{3304 + index:05d}.bin').write_bytes(b)
            w.writerow({'entry': 3304 + index, 'sha256': hashlib.sha256(b).hexdigest(),
                        'status': 'PARSED'})
    with groups.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['start_entry', 'end_entry', 'record_count',
                                          'forms', 'locale_order', 'evidence_grade', 'category'])
        w.writeheader()
        w.writerow({'start_entry': 3304, 'end_entry': 3312, 'record_count': 2,
                    'forms': forms, 'locale_order': ','.join(LANGS),
                    'evidence_grade': 'STRUCTURE_AND_SCRIPT_WITNESS',
                    'category': 'UNKNOWN'})
    return decoded, groups, inventory


class NativeTextFiles(unittest.TestCase):
    def test_one_line_per_record_and_lossless_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            decoded, groups, inventory = fixture(root)
            report = run(decoded, groups, inventory, root / 'out', {3304})
            self.assertEqual(report['groups_exported'], 1)
            folder = root / 'out' / 'table_03304'
            self.assertEqual((folder / 'jp.txt').read_text(encoding='utf-8'),
                             'Line one\\\\literal\\nwith newline\n\n')
            records = [json.loads(line) for line in
                       (folder / 'jp.forms.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(records[0]['forms'], ['Line one\\literal\nwith newline'])
            self.assertEqual(records[1]['forms'], [''])

    def test_six_forms_and_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            decoded, groups, inventory = fixture(root, forms=6)
            run(decoded, groups, inventory, root / 'out', {3304})
            record = json.loads((root / 'out/table_03304/zhs.forms.jsonl')
                                .read_text(encoding='utf-8').splitlines()[0])
            self.assertEqual(record['forms'], ['First', 'One\tTwo', '三', '', 'x', '🎮'])
            self.assertEqual(record['raw_metadata_u32'], [0xab, 0xcd])
            self.assertEqual(len(record['absolute_byte_offsets']), 6)

    def test_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            decoded, groups, inventory = fixture(root)
            inventory.write_text(
                inventory.read_text(encoding='utf-8').replace('PARSED', 'INVALID', 1),
                encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'SHA/status mismatch'):
                run(decoded, groups, inventory, root / 'out', {3304})

    def test_unknown_group_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            decoded, groups, inventory = fixture(root)
            with self.assertRaisesRegex(ValueError, 'groups missing'):
                run(decoded, groups, inventory, root / 'out', {9999})


if __name__ == '__main__':
    unittest.main()
