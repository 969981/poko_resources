"""Synthetic format-level tests. Real Pokopia samples run in CI separately."""
import csv
import io
import struct
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from Scripts.resources import g1t_to_png as m


def synthetic_g1t(w=64, h=64):
    assert w == h == 64
    data = bytearray(0x34 + 4096)
    data[:8] = b"GT1G0600"
    struct.pack_into("<IIII", data, 8, len(data), 0x1c, 1, 0x18)
    struct.pack_into("<I", data, 0x1c, 4)
    data[0x20:0x28] = bytes([0x10, 0x66, 0x66, 0, 0x11, 0x10, 0x21, 0x10])
    struct.pack_into("<I", data, 0x28, 12)
    return bytes(data)


class G1TTests(unittest.TestCase):
    def test_parse_real_shape_and_platform(self):
        platform, tex = m.parse_g1t(synthetic_g1t())
        self.assertEqual(platform, 0x18)
        self.assertEqual(len(tex), 1)
        self.assertEqual(tex[0]["format"], 0x66)
        self.assertEqual((tex[0]["width"], tex[0]["height"]), (64, 64))
        self.assertEqual(len(tex[0]["payload"]), 4096)

    def test_corrupt_header_rejected(self):
        self.assertRaises(ValueError, m.parse_g1t, b"GT1G")
        self.assertRaises(ValueError, m.parse_g1t, b"NOPE" + synthetic_g1t()[4:])

    def test_bc7_to_png_variants(self):
        _, tex = m.parse_g1t(synthetic_g1t())
        for layout in ("linear", "gob1", "gob2"):
            data = m.decode_png(tex[0]["payload"], 64, 64, layout)
            with Image.open(io.BytesIO(data)) as im:
                self.assertEqual(im.format, "PNG")
                self.assertEqual(im.size, (64, 64))
                self.assertEqual(im.getpixel((0, 0)), (0, 0, 0, 255))

    def test_gob_changes_block_order(self):
        source = bytes((i * 37) % 256 for i in range(4096))
        self.assertNotEqual(m.unswizzle_gob_bc7(source, 64, 64, 1), source)
        self.assertEqual(len(m.unswizzle_gob_bc7(source, 64, 64, 2)), 4096)

    def test_texinfo_name_is_unlinked_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "root_001120_048fc972.texinfo").write_bytes(
                struct.pack("<I", 1) + b"item_1425_m\0".ljust(104, b"\0")
            )
            output = root / "texinfo_names.csv"
            self.assertEqual(m.texinfo_index(root, output), 1)
            with output.open(encoding="utf-8", newline="") as f:
                row = list(csv.DictReader(f))[0]
            self.assertEqual(row["texture_name"], "item_1425_m")
            self.assertEqual(row["item_id_candidate"], "1425")
            self.assertEqual(row["link_status"], "NAME_ONLY_UNLINKED")


if __name__ == "__main__":
    unittest.main()
