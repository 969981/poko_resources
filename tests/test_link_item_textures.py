"""Join tests use synthetic metadata; CI separately checks the 2.0.1 indexes."""
import unittest

from Scripts.resources.link_item_textures import make_links


class LinkItemTexturesTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [
            {"item_id": "6", "zhs": "成熟的蘑菇", "en": "cave mushrooms",
             "has_pokohex_icon": "1"},
            {"item_id": "7", "zhs": "海藻", "en": "seaweed",
             "has_pokohex_icon": "0"},
        ]
        self.name = [
            {"texinfo_path": "test/root_000123_deadbeef.texinfo",
             "texture_name": "item_0006", "record_index": "0",
             "record_count": "2", "atlas_u0": "0", "atlas_v0": "0",
             "atlas_u1": "0.125", "atlas_v1": "0.125", "uv_status": "RECT_OK"},
            {"texinfo_path": "test/root_000123_deadbeef.texinfo",
             "texture_name": "item_0007", "record_index": "1",
             "record_count": "2", "atlas_u0": "0.125", "atlas_v0": "0",
             "atlas_u1": "0.25", "atlas_v1": "0.125", "uv_status": "RECT_OK"},
        ]
        self.mapping = [
            {"item_id": str(i), "sprite_name": f"item_{i:04d}",
             "variant": "", "texinfo_hash": "deadbeef", "g1t_hash": "1234abcd",
             "g1t_pack": "0x00011c54.fdata", "g1t_bytes": "4096",
             "g1t_index_match": "True"}
            for i in (6, 7)
        ]
        self.layout = [{"texinfo_hash": "deadbeef", "g1t_hash": "1234abcd",
                        "objdb_file": "sample.kidsobjdb", "object_hash": "4567abcd"}]

    def test_shared_atlas_is_cropped_per_sprite(self):
        rows, audit = make_links(self.name, self.mapping, self.layout, self.catalog)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["link_evidence"], "TEXINFO_NAME_UV_AND_LAYOUT_INDEX")
        self.assertEqual(rows[1]["atlas_u0"], "0.125")
        self.assertEqual(rows[1]["texinfo_record_index"], "1")
        self.assertEqual(rows[0]["g1t_hash"], rows[1]["g1t_hash"])
        self.assertEqual(audit["atlas_record_link_rows"], 2)
        self.assertEqual(audit["missing_png_items_in_current_map"], 1)

    def test_missing_layout_link_is_not_silently_accepted(self):
        with self.assertRaises(ValueError):
            make_links(self.name, self.mapping, [], self.catalog)

    def test_missing_texinfo_name_remains_only_index_evidence(self):
        rows, audit = make_links([], self.mapping, self.layout, self.catalog)
        self.assertEqual(audit["texinfo_record_matches"], 0)
        self.assertEqual(rows[0]["link_evidence"],
                         "LAYOUT_INDEX_ONLY_TEXINFO_NOT_SCANNED")

    def test_id_mismatch_is_rejected(self):
        self.mapping[0]["sprite_name"] = "item_0009"
        with self.assertRaises(ValueError):
            make_links(self.name, self.mapping, self.layout, self.catalog)


if __name__ == "__main__":
    unittest.main()
