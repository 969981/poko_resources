"""Non-item TEXINFO classification and unique KIDSOBJDB->G1T index tests."""
import unittest
from Scripts.resources.build_native_misc_texture_index import eligible,family_kind,index_rows


class MiscSpriteIndexTests(unittest.TestCase):
    def test_items_and_pokemon_excluded_but_not_materials(self):
        self.assertFalse(eligible("item_0006"))
        self.assertFalse(eligible("item_1425_m"))
        self.assertFalse(eligible("icon_poke_0082_00_00_00"))
        self.assertFalse(eligible("icon_poke_uni_0180_00_00_00"))
        self.assertTrue(eligible("icon_material_0001"))
        self.assertEqual(family_kind("icon_material_0001"),"material_name_candidate")
        self.assertEqual(family_kind("icon_house"),"ui_icon_name_candidate")

    def test_original_hash_path_and_uv_linkage_preserved(self):
        prefix="UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/"
        tex=prefix+"root_000100_abcdef12.texinfo"
        g1t=prefix+"root_000200_12345678.g1t"
        textures=[dict(texture_name="icon_material_test",family="icon",
            texinfo_path=tex,record_index="0",record_count="1",
            texture_layer_raw_u32="0",uv_status="RECT_OK",
            atlas_u0="0",atlas_v0="0",atlas_u1="0.5",atlas_v1="0.5"),
            dict(texture_name="item_0006",family="item",texinfo_path=tex,
            record_index="1",record_count="2",texture_layer_raw_u32="0",
            uv_status="RECT_OK",atlas_u0="0",atlas_v0="0",atlas_u1="1",atlas_v1="1")]
        maps=[dict(texinfo_hash="abcdef12",g1t_hash="12345678",
                   object_hash="deadbeef",objdb_file="d.kidsobjdb")]
        result=index_rows(textures,maps,[tex,g1t])
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]["status"],"INDEXED_ORIGINAL_TEXINFO_G1T_PAIR")
        self.assertEqual(result[0]["g1t_path"],g1t)
        self.assertEqual(result[0]["texinfo_hash"],"abcdef12")
        self.assertEqual(result[0]["uv_u1"],"0.5")

    def test_multiple_g1t_edges_are_explicitly_ambiguous(self):
        src="x/root_000100_abcdef12.texinfo"
        row=dict(texture_name="icon_house",family="icon",texinfo_path=src,
            record_index="0",record_count="1",texture_layer_raw_u32="0",
            uv_status="RECT_OK",atlas_u0="0",atlas_v0="0",atlas_u1="1",atlas_v1="1")
        edges=[dict(texinfo_hash="abcdef12",g1t_hash=h,object_hash="1",objdb_file="x")
               for h in ("11111111","22222222")]
        out=index_rows([row],edges,[src,"x/root_001000_11111111.g1t","x/root_001002_22222222.g1t"])
        self.assertEqual(out[0]["status"],"MISSING_OR_AMBIGUOUS_KIDSOBJDB_INDEX_EDGE")
        self.assertFalse(out[0]["g1t_path"])


if __name__=="__main__":
    unittest.main()
