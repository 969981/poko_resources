"""Targeted KIDSOBJDB binary layout evidence is size/byte-bound guarded."""
import struct
import unittest

from Scripts.unpack.m4_diagnostics import bounded_blocks
from Scripts.unpack.core import FormatError


class DiagnosticTests(unittest.TestCase):
    def test_rdok_28_byte_block_has_four_unlabeled_words(self):
        payload = b"RDOK0000" + struct.pack("<I4I", 28, 0x01010101, 2, 3, 0xffffffff)
        doc = b"_DOK0000" + struct.pack("<5I", 28, 2, 1, 0xaaaa, 56) + payload
        result = bounded_blocks(doc)
        self.assertEqual(result["blocks"][0]["kind"], "RDOK0000")
        self.assertEqual(result["blocks"][0]["payload_size"], 16)
        self.assertEqual(result["blocks"][0]["words_u32_hex"][3], "ffffffff")
        self.assertEqual(result["end_offset"], 56)

    def test_invalid_idok_count_is_represented_without_guessing(self):
        payload = (b"IDOK0000" + struct.pack("<4I", 36, 0xaa, 0xbb, 1)
                   + struct.pack("<3I", 5, 0xffffffff, 0x1234))
        doc = b"_DOK0000" + struct.pack("<5I", 28, 2, 1, 0, 64) + payload
        result = bounded_blocks(doc)
        self.assertEqual(result["blocks"][0]["first_property_count"], 0xffffffff)
        self.assertEqual(result["blocks"][0]["size"], 36)

    def test_truncated_doc_rejected(self):
        with self.assertRaisesRegex(FormatError, "INVALID_DOK"):
            bounded_blocks(b"bad")


if __name__ == "__main__":
    unittest.main()
