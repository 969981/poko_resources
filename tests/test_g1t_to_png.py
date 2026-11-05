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

    def test_bc3_dxt5_to_png(self):
        data = m.decode_png(bytes(4096), 64, 64, "linear", 0x62)
        with Image.open(io.BytesIO(data)) as im:
            self.assertEqual(im.size, (64, 64))
            self.assertEqual(im.format, "PNG")
            self.assertEqual(im.getpixel((0, 0)), (0, 0, 0, 0))

    def test_morton_block_permutation_and_axis_variant(self):
        # 8x8 BC blocks, one color-tagged 16-byte compressed block per source index.
        src = b"".join(bytes([i])*16 for i in range(64))
        plain = m.unswizzle_morton_bc(src, 32, 32)
        transpose = m.unswizzle_morton_bc(src, 32, 32, swap_axes=True)
        tagged = lambda buf, x, y: buf[(y*8+x)*16]
        self.assertEqual(tagged(plain, 0, 0), 0)
        self.assertEqual(tagged(plain, 1, 0), 1)
        self.assertEqual(tagged(plain, 0, 1), 2)
        self.assertEqual(tagged(transpose, 1, 0), 2)
        self.assertEqual(tagged(transpose, 0, 1), 1)
        tiled = m.unswizzle_morton_bc(src, 32, 32, tile_blocks=4)
        self.assertEqual(tagged(tiled, 4, 0), 16)
        self.assertEqual(len(tiled), len(src))
        with self.assertRaises(ValueError):
            m.unswizzle_morton_bc(src[:16], 32, 32)

    def test_gob_changes_block_order(self):
        source = bytes((i * 37) % 256 for i in range(4096))
        self.assertNotEqual(m.unswizzle_gob_bc7(source, 64, 64, 1), source)
        self.assertEqual(len(m.unswizzle_gob_bc7(source, 64, 64, 2)), 4096)


    def test_ounce_bc7_switch2_gob_bit_order(self):
        # Original 2.0.1 reference alignment proves a swap of x0 and y1
        # address bits relative to legacy Tegra GOB byte addresses.
        blocks = 16 * 16
        source = b"".join(bytes([i]) * 16 for i in range(blocks))
        untiled = m.unswizzle_ounce_bc7(source, 64, 64, 2)
        get = lambda x, y: untiled[(y * 16 + x) * 16]
        self.assertEqual([get(x, 0) for x in range(5)], [0, 4, 16, 20, 64])
        self.assertEqual([get(0, y) for y in range(9)],
                         [0, 1, 2, 3, 8, 9, 10, 11, 32])
        self.assertEqual(set(untiled[::16]), set(range(blocks)))
        legacy = m.unswizzle_gob_bc7(source, 64, 64, 2)
        self.assertNotEqual(untiled, legacy)
        self.assertEqual(legacy[(1 * 16 + 0) * 16], 1)
        self.assertEqual(legacy[(2 * 16 + 0) * 16], 4)

    def test_ounce_bgra_addresses_are_distinct_and_in_bounds(self):
        source = b"".join(i.to_bytes(4, "little") for i in range(256))
        untiled = m.unswizzle_ounce_raw_bgra(source, 16, 16, 1)
        sample = lambda x, y: int.from_bytes(untiled[(y * 16 + x) * 4:
                                                       (y * 16 + x + 1) * 4], "little")
        self.assertEqual([sample(0, y) for y in range(5)], [0, 4, 8, 12, 32])
        self.assertEqual(sample(4, 0), 16)
        self.assertEqual(set(int.from_bytes(untiled[i:i + 4], "little")
                             for i in range(0, len(untiled), 4)), set(range(256)))

    def test_ounce_bc7_rejects_truncated_surface(self):
        with self.assertRaisesRegex(ValueError, "surface requires"):
            m.unswizzle_ounce_bc7(bytes(1024), 64, 64, 2)
        with self.assertRaises(ValueError):
            m.unswizzle_ounce_bc7(bytes(4096), 64, 64, 3)

    def test_ounce_decode_produces_rgba_png(self):
        png = m.decode_png(bytes(4096), 64, 64, "ounce2", 0x66)
        with Image.open(io.BytesIO(png)) as img:
            self.assertEqual((img.format, img.size), ("PNG", (64, 64)))

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


    def test_multi_record_texinfo_atlas_uv(self):
        data = bytearray(4 + 2 * 104)
        struct.pack_into("<I", data, 0, 2)
        for i, name in enumerate(("item_0006", "item_0007")):
            start = 4 + i * 104
            data[start:start + len(name)] = name.encode("ascii")
            u0 = i * 0.125
            u1 = u0 + 0.125
            v0, v1 = 0.25, 0.5
            struct.pack_into("<8f", data, start + 68,
                             u0, v0, u1, v0, u0, v1, u1, v1)
            struct.pack_into("<I", data, start + 100, 1)
        records = m.parse_texinfo(bytes(data))
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["record_count"], 2)
        self.assertEqual(records[1]["record_index"], 1)
        self.assertEqual(records[1]["name"], "item_0007")
        self.assertEqual(records[1]["uv_status"], "RECT_OK")
        self.assertAlmostEqual(records[1]["u0"], 0.125)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "root_000001_abcd1234.texinfo").write_bytes(data)
            path = root / "index.csv"
            self.assertEqual(m.texinfo_index(root, path), 2)
            with path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([r["texture_name"] for r in rows],
                             ["item_0006", "item_0007"])
            self.assertEqual(rows[1]["record_count"], "2")
            self.assertEqual(rows[1]["atlas_u0"], "0.125")

    def test_texinfo_corrupt_record_count_fails_closed(self):
        blob = bytearray(4 + 104)
        struct.pack_into("<I", blob, 0, 1333)
        with self.assertRaises(ValueError):
            m.parse_texinfo(bytes(blob))


if __name__ == "__main__":
    unittest.main()
