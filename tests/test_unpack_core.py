"""Small synthetic fixtures and a byte-exact verification vector from a real v2.0.1 FDATA.

The real sample is limited to one 88-byte compressed record, not a ROM archive.
"""
import hashlib
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from Scripts.unpack.core import (
    FormatError, decode_linkdata_payload, decode_kt_payload, kt_zlib_chunks,
    parse_idx, parse_rdb, parse_rdx, read_idrk,
)
from Scripts.unpack.inventory import audit as audit_inventory
from Scripts.unpack.linkdata import run as run_linkdata
from Scripts.unpack.ktrdb import run as run_ktrdb


# 96-byte output, sourced from a 2.0.1 KIDSOBJDB record in 0x4b13d561.fdata.
# Contains a 10-byte KT chunk header + a zlib stream + 2 bytes of zero padding.
REAL_KT_COMPRESSED_HEX = (
    '4c00a4c6a44026d4afa6789c8b77f1f7360002190606060920660462fdaf5f2f2500'
    '694fa89c0b90cdfee67ea5e3b3a54acc40362b0304acded697cb0ad5e371bf360a'
    'c6de3f4bf5bc6df34d9fbdf314ac00d34516370000'
)


def synth_rdb(name, typehash, offset, size, fidx=0, footer=0x401):
    foot = struct.pack('<HIIHB', footer, offset, size, fidx, 0)
    entry_size = 48 + len(foot)
    row = (b'IDRK0000' + struct.pack('<QQQ', entry_size, 13, 96)
           + struct.pack('<IIII', 1, name, typehash, 0) + foot)
    row += b'\0' * ((-len(row)) % 4)
    header = b'_DRK0000' + struct.pack('<4I', 32, 0, 1, 0) + bytes(8)
    return header + row


class TestFormatReaders(unittest.TestCase):
    def test_idx_alignment(self):
        blob = (struct.pack('<4Q', 0, 8, 8, 0)
                + struct.pack('<4Q', 256, 22, 25, 1)
                + struct.pack('<4Q', 512, 0, 0, 0))
        a = parse_idx(blob)
        self.assertEqual(len(a), 3)
        self.assertEqual(a[1].flag, 1)
        with self.assertRaisesRegex(FormatError, 'IDX_OFFSET_ALIGNMENT_MISMATCH'):
            parse_idx(blob[:32] + struct.pack('<4Q', 16, 1, 1, 0))
        with self.assertRaisesRegex(FormatError, 'IDX_SIZE_NOT_MULTIPLE_OF_32'):
            parse_idx(blob + b'1')

    def test_rdx_rdb(self):
        rdx = parse_rdx(struct.pack('<HHI', 0, 0xffff, 0x4b13d561))
        self.assertEqual(rdx[0].filename, '0x4b13d561.fdata')
        rdb = synth_rdb(0xf79cb076, 0x20a6a0bb, 16, 157)
        entries, head = parse_rdb(rdb, 'root', rdx)
        self.assertEqual(head['parsed'], 1)
        self.assertEqual(entries[0].fdata_offset, 16)
        self.assertEqual(entries[0].type_hash, 0x20a6a0bb)
        with self.assertRaisesRegex(FormatError, 'RDB_INVALID_RDX_POSITION'):
            parse_rdb(synth_rdb(1, 2, 16, 157, fidx=1), 'root', rdx)

    def test_rdb_extended_17_byte_footer_is_opaque(self):
        rdx = parse_rdx(struct.pack('<HHI', 0, 0xffff, 0x4b13d561))
        real_footer = bytes.fromhex('010400000080409f048741120000000000')
        row_len = 48 + len(real_footer)
        header = b'_DRK0000' + struct.pack('<4I', 32, 0, 1, 0) + bytes(8)
        record = b'IDRK0000' + struct.pack('<QQQIIII', row_len, len(real_footer), 96,
                                           1, 0xf79cb076, 0x20a6a0bb, 0) + real_footer
        record += bytes((-len(record)) % 4)
        entries, _ = parse_rdb(header + record, 'root', rdx)
        self.assertEqual(entries[0].footer_layout, 'opaque_17')
        self.assertEqual(entries[0].footer_extra_hex, real_footer.hex())
        self.assertEqual(entries[0].fdata_index, -1)

    def test_real_kt_frame(self):
        compressed = bytes.fromhex(REAL_KT_COMPRESSED_HEX)
        decoded = kt_zlib_chunks(compressed, 96, 0x400000)
        self.assertEqual(len(decoded), 96)
        self.assertTrue(decoded.startswith(b'_DOK0000'))
        with self.assertRaises(FormatError):
            kt_zlib_chunks(compressed[:-2] + b'\0\x01', 96, 0x400000)
        with self.assertRaises(FormatError):
            kt_zlib_chunks(compressed, 97, 0x400000)

    def test_linkdata_zlib_and_raw(self):
        raw = b'hello, linkdata!'
        self.assertEqual(decode_linkdata_payload(raw, len(raw), 0), raw)
        self.assertEqual(decode_linkdata_payload(zlib.compress(raw), len(raw), 1), raw)
        with self.assertRaises(FormatError):
            decode_linkdata_payload(b'broken', len(raw), 1)
        with self.assertRaises(FormatError):
            decode_linkdata_payload(raw, len(raw), 9)

    def test_idrk_record_and_kt_end_to_end(self):
        payload = bytes.fromhex(REAL_KT_COMPRESSED_HEX)
        meta = bytes(21)
        header = b'IDRK0000' + struct.pack('<QQQIIII', 48 + len(meta) + len(payload), len(payload), 96,
                                            1, 0xf79cb076, 0x20a6a0bb, 0x400000)
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'sample.fdata'
            src.write_bytes(b'PDRK0000' + struct.pack('<II', 16, 0) + header + meta + payload)
            with src.open('rb') as f:
                h, m = read_idrk(f, 16, src.stat().st_size)
                dec = decode_kt_payload(f.read(h.packed_size), h)
            self.assertEqual(h.header_bytes, 21)
            self.assertEqual(h.name_hash, 0xf79cb076)
            self.assertEqual(len(dec), 96)
            self.assertEqual(m, meta)

    def test_linkdata_batch_resume(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            raw = b'abcd' * 4
            comp = zlib.compress(raw)
            (p / 'test.idx').write_bytes(struct.pack('<4Q', 0, 16, len(comp), 1))
            (p / 'test.bin').write_bytes(comp + bytes(256 - len(comp)))
            a = run_linkdata(p / 'test.idx', p / 'test.bin', p / 'out', 0, None, False, True, False)
            b = run_linkdata(p / 'test.idx', p / 'test.bin', p / 'out', 0, None, False, True, True)
            self.assertEqual(a['statuses'], {'DECOMPRESSED': 1})
            self.assertEqual(b['statuses'], a['statuses'])
            self.assertEqual((p / 'out/decoded/00000.bin').read_bytes(), raw)

    def test_ktrdb_batch_real_frame_synthetic_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); base = p / 'KIDS_PLATFORM_OUNCE'; base.mkdir()
            payload = bytes.fromhex(REAL_KT_COMPRESSED_HEX)
            entry_size = 48 + 21 + len(payload)
            header = b'IDRK0000' + struct.pack('<QQQIIII', entry_size, len(payload), 96,
                                                1, 0xf79cb076, 0x20a6a0bb, 0x400000)
            (base / '0x4b13d561.fdata').write_bytes(b'PDRK0000' + struct.pack('<II', 16, 0) + header + bytes(21) + payload)
            (base / 'root.rdx').write_bytes(struct.pack('<HHI', 0, 0xffff, 0x4b13d561))
            (base / 'root.rdb').write_bytes(synth_rdb(0xf79cb076, 0x20a6a0bb, 16, entry_size))
            (base / 'system.rdx').write_bytes(b'')
            (base / 'system.rdb').write_bytes(b'_DRK0000' + struct.pack('<4I', 32, 0, 0, 0) + bytes(8))
            report = run_ktrdb(base, p / 'out', True, True, None, False, False)
            self.assertEqual(report['statuses'], {'DECOMPRESSED': 1})
            self.assertEqual(len(list((p / 'out/decoded').glob('*.bin'))), 1)

    def test_linkdata_verify_only_writes_no_asset(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            value = b'verified-only' * 6
            packed = zlib.compress(value)
            (p / 'a.idx').write_bytes(struct.pack('<4Q', 0, len(value), len(packed), 1))
            (p / 'a.bin').write_bytes(packed)
            report = run_linkdata(p / 'a.idx', p / 'a.bin', p / 'meta', 0, None,
                                  False, True, False, True)
            self.assertEqual(report['statuses'], {'DECOMPRESSED': 1})
            self.assertFalse((p / 'meta/raw').exists())
            self.assertFalse((p / 'meta/decoded').exists())
            self.assertTrue((p / 'meta/linkdata_entries.csv').is_file())

    def test_ktrdb_fdata_filter_and_verify_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); base = p / 'root'; base.mkdir()
            payload = bytes.fromhex(REAL_KT_COMPRESSED_HEX)
            entry_size = 48 + 21 + len(payload)
            header = b'IDRK0000' + struct.pack('<QQQIIII', entry_size, len(payload), 96,
                                                1, 0xf79cb076, 0x20a6a0bb, 0x400000)
            (base / '0x4b13d561.fdata').write_bytes(b'PDRK0000' + struct.pack('<II', 16, 0) + header + bytes(21) + payload)
            (base / 'root.rdx').write_bytes(struct.pack('<HHI', 0, 0xffff, 0x4b13d561))
            (base / 'root.rdb').write_bytes(synth_rdb(0xf79cb076, 0x20a6a0bb, 16, entry_size))
            (base / 'system.rdx').write_bytes(b'')
            (base / 'system.rdb').write_bytes(b'_DRK0000' + struct.pack('<4I', 32, 0, 0, 0) + bytes(8))
            report = run_ktrdb(base, p / 'meta', True, True, None, False, False, True, {'4b13d561'})
            self.assertEqual(report['statuses'], {'DECOMPRESSED': 1})
            self.assertFalse((p / 'meta/raw').exists())
            self.assertFalse((p / 'meta/decoded').exists())
            skipped = run_ktrdb(base, p / 'meta2', True, True, None, False, False, True, {'ffffffff'})
            self.assertEqual(skipped['statuses'], {'LOCATED': 1})

    def test_inventory_missing_split_part(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); src = p / '2.0.1'; src.mkdir()
            (src / 'a.7z.001').write_bytes(b'AAA')
            (src / 'a.7z.003').write_bytes(b'BBB')
            report = audit_inventory(src, p / '_meta', True, False)
            self.assertFalse(report['continuity_ok'])
            self.assertEqual(report['volume_sets'], 1)
            self.assertEqual(len(report['validation_failures']), 1)


if __name__ == '__main__':
    unittest.main()
