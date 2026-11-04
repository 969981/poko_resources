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
