"""Regression tests for native Pokopia TEXINFO name-to-sprite linkage.

The legacy audit previously looked at only the first 104-byte TEXINFO record,
falsely rejecting hundreds of valid sprites in shared native texture atlases.
"""
from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from Scripts.resources import trace_item_textures as m


def texinfo(*names: str, duplicate: bool = False) -> bytes:
    data = bytearray(4 + 104 * len(names))
    struct.pack_into("<I", data, 0, len(names))
    for i, name in enumerate(names):
        base = 4 + i * 104
        raw = name.encode("ascii")
        if len(raw) >= 64:
            raise ValueError("synthetic name too long")
        data[base:base + len(raw)] = raw
        struct.pack_into("<I", data, base + 64, i % 2)
        u0, u1 = i / max(len(names), 1), (i + 1) / max(len(names), 1)
        struct.pack_into("<8f", data, base + 68,
                         u0, 0.0, u1, 0.0, u0, 0.5, u1, 0.5)
    return bytes(data)


class TraceTexinfoTests(unittest.TestCase):
    def test_multi_record_atlas_matches_nonfirst_sprite(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "atlas.texinfo"
            file.write_bytes(texinfo("item_0006", "item_0007", "item_0008"))
            row = m.texinfo_sprite(file, "item_0008")
            self.assertIsNotNone(row)
            self.assertEqual(row["record_index"], 2)
            self.assertEqual(row["record_count"], 3)
            self.assertEqual(row["uv_status"], "RECT_OK")
            self.assertEqual(row["texture_layer_raw_u32"], 0)
            self.assertIsNone(m.texinfo_sprite(file, "item_9999"))

    def test_single_record_backwards_compatible(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "single.texinfo"
            file.write_bytes(texinfo("item_1425_m"))
            row = m.texinfo_sprite(file, "item_1425_m")
            self.assertEqual((row["record_index"], row["record_count"]), (0, 1))
            self.assertEqual(len(m.texinfo_records(str(file))), 1)

    def test_duplicate_sprite_rejected_instead_of_guessing(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "ambiguous.texinfo"
            file.write_bytes(texinfo("item_0006", "item_0006"))
            with self.assertRaisesRegex(ValueError, "duplicate TEXINFO"):
                m.texinfo_sprite(file, "item_0006")

    def test_corrupt_record_count_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            file = Path(d) / "bad.texinfo"
            bad = bytearray(texinfo("item_0006"))
            struct.pack_into("<I", bad, 0, 1333)
            file.write_bytes(bad)
            with self.assertRaisesRegex(ValueError, "count/size mismatch"):
                m.texinfo_sprite(file, "item_0006")


if __name__ == "__main__":
    unittest.main()
