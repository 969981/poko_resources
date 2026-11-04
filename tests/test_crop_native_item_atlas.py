"""No emulator or game files needed: test atlas layer split and UV geometry."""
import unittest
from PIL import Image
from Scripts.resources.crop_native_item_atlas import crop_uv, split_bc_layers


class CropAtlasTests(unittest.TestCase):
    def test_two_exact_layers(self):
        layers = split_bc_layers(bytes(range(32)), 4, 4, 2)
        self.assertEqual(layers, [bytes(range(16)), bytes(range(16, 32))])
        with self.assertRaises(ValueError):
            split_bc_layers(bytes(31), 4, 4, 2)

    def test_two_independent_g1t_entries(self):
        # G1T table starts at 0x1c. Each entry has its own 8-byte header,
        # 12-byte extra header and BC payload (one 4x4 BC7 block).
        import struct
        from Scripts.resources.g1t_to_png import parse_g1t
        file = bytearray(0x24)
        file[:8] = b"GT1G0600"
        texture0 = bytes([0x10, 0x66, 0x22, 0, 0, 0, 0, 1]) + struct.pack("<I", 12) + bytes(8) + bytes([0xA0]) * 16
        texture1 = bytes([0x10, 0x66, 0x22, 0, 0, 0, 0, 1]) + struct.pack("<I", 12) + bytes(8) + bytes([0xB0]) * 16
        struct.pack_into("<IIII", file, 8, len(file) + len(texture0) + len(texture1), 0x1c, 2, 0x18)
        struct.pack_into("<II", file, 0x1c, 8, 8 + len(texture0))
        platform, layers = parse_g1t(bytes(file) + texture0 + texture1)
        self.assertEqual(platform, 0x18)
        self.assertEqual(len(layers), 2)
        self.assertEqual([len(t["payload"]) for t in layers], [16, 16])
        self.assertEqual(layers[0]["payload"], bytes([0xA0]) * 16)
        self.assertEqual(layers[1]["payload"], bytes([0xB0]) * 16)

    def test_crop_uses_native_uv_and_vertical_origin(self):
        image = Image.new("RGBA", (100, 100), "red")
        entry = {"uv_u0": "0", "uv_v0": "0",
                 "uv_u1": "0.25", "uv_v1": "0.5"}
        cropped, rect = crop_uv(image, entry)
        self.assertEqual(rect, (0, 0, 25, 50))
        self.assertEqual(cropped.size, (25, 50))
        _, flipped = crop_uv(image, entry, flip_v=True)
        self.assertEqual(flipped, (0, 50, 25, 100))

    def test_invalid_rect_fails_not_silent_crop(self):
        with self.assertRaises(ValueError):
            crop_uv(Image.new("RGBA", (10, 10)),
                    {"uv_u0": "0.6", "uv_v0": "0",
                     "uv_u1": "0.2", "uv_v1": "1"})


if __name__ == "__main__":
    unittest.main()
