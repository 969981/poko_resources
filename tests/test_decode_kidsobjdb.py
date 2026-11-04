"""KIDSOBJDB structural decoding regressions; RDOK remains explicitly opaque."""
import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

from Scripts.unpack.core import FormatError
from Scripts.unpack.decode_kidsobjdb import parse, run


def make_doc(blocks, declared=None):
    size = 28 + sum((len(block) + 3) // 4 * 4 for block in blocks)
    header = b"_DOK0000" + struct.pack("<5I", 28, 1, len(blocks), 0xabcdef12, size if declared is None else declared)
    data = bytearray(header)
    for block in blocks:
        data.extend(block)
        data.extend(b"\x00" * (-len(data) % 4))
    return bytes(data)


class KidsObjDBTests(unittest.TestCase):
    def test_realistic_96_byte_idok_fixed_width(self):
        values = list(range(8))
        block = (b"IDOK0000" + struct.pack("<4I", 68, 0x11223344, 0x55667788, 1)
                 + struct.pack("<3I", 5, 8, 0xaabbccdd)
                 + struct.pack("<8I", *values))
        document = make_doc([block])
        self.assertEqual(len(document), 96)
        parsed = parse(document)
        self.assertEqual(parsed["header"]["entry_count"], 1)
        self.assertEqual(parsed["summary"]["IDOK"], 1)
        self.assertEqual(parsed["semantic_status"], "FIXED_WIDTH_ONLY")
        field = parsed["blocks"][0]["properties"][0]
        self.assertEqual(field["sample_values"], values)
        self.assertEqual(parsed["sha256"], hashlib.sha256(document).hexdigest())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "one.kidsobjdb"
            path.write_bytes(document)
            result = run(path, Path(tmp) / "decoded.json")
            self.assertEqual(result["summary"]["PARTIAL_BLOCKS"], 0)
            self.assertTrue((Path(tmp) / "decoded.json").is_file())

    def test_rdok_preserves_structure_without_claiming_semantic_decode(self):
        r = parse(make_doc([b"RDOK0000" + struct.pack("<I", 12)]))
        self.assertEqual(r["summary"]["RDOK"], 1)
        self.assertEqual(r["blocks"][0]["status"], "RDOK_OPAQUE")
        self.assertEqual(r["semantic_status"], "PARTIAL_UNSUPPORTED_OR_RDOK")

    def test_unsupported_type_explicit(self):
        block = (b"IDOK0000" + struct.pack("<4I", 36, 1, 2, 1)
                 + struct.pack("<3I", 99, 0, 3))
        r = parse(make_doc([block]))
        self.assertEqual(r["summary"]["UNSUPPORTED_TYPES"], 1)
        self.assertEqual(r["blocks"][0]["properties"][0]["status"], "UNSUPPORTED_TYPE")

    def test_reject_truncated_idok_block(self):
        broken = (b"IDOK0000" + struct.pack("<4I", 36, 1, 2, 1)
                  + struct.pack("<3I", 5, 100, 3))
        with self.assertRaisesRegex(FormatError, "PROPERTY_DATA_TRUNCATED"):
            parse(make_doc([broken]))

    def test_reject_bad_magic(self):
        with self.assertRaisesRegex(FormatError, "INVALID_HEADER"):
            parse(b"bad" * 20)

    def test_reject_corrupt_block_size(self):
        doc = make_doc([b"RDOK0000" + struct.pack("<I", 123456)])
        with self.assertRaisesRegex(FormatError, "BLOCK_SIZE_INVALID"):
            parse(doc)


if __name__ == "__main__":
    unittest.main()
