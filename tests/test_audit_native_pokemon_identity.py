"""Source-linked identity audit must not turn texture name digits into species IDs."""
import unittest
from Scripts.resources.audit_native_pokemon_identity import build


class PokemonIdentityAuditTests(unittest.TestCase):
    def test_preserves_name_hash_identity_and_unverified_species(self):
        original = [
            {"texture_name": "icon_poke_0082_00_00_00", "texinfo_hash": "abcdef12",
             "g1t_hash": "12345678", "category": "pokemon",
             "texture_number_candidate": "0082", "texinfo_filename":"native_a.texinfo",
             "g1t_filename":"native_b.g1t", "texinfo_record_index":"0",
             "texture_layer":"0", "native_source_kind":"ORIGINAL_NATIVE_G1T",
             "status":"PHYSICAL_G1T_PRESENT"}
        ]
        manifest = [{"texture_name":"icon_poke_0082_00_00_00",
                     "texinfo_hash":"abcdef12", "g1t_hash":"12345678",
                     "png_path":"x.png", "png_sha256":"c"*64,
                     "swizzle_layout":"ounce8", "status":"PNG_CANDIDATE_UNVERIFIED"}]
        edge = [{"texinfo_hash":"abcdef12", "g1t_hash":"12345678",
                 "object_hash":"deadbeef", "objdb_file":"source.kidsobjdb"}]
        found = build(original, manifest, edge)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["link_status"],"INDEX_PNG_AND_HASH_EDGE_LINKED")
        self.assertEqual(found[0]["object_hash"],"deadbeef")
        self.assertEqual(found[0]["texture_number_candidate"],"0082")
        self.assertEqual(found[0]["native_species_id_verified"],"")
        self.assertEqual(found[0]["swizzle_layout"],"ounce8")

    def test_preserve_duplicate_resource_names_and_report_ambiguous_edges(self):
        index = []
        sources = []
        for tex,g1t in [("aaaa1234","11111111"),("bbbb1234","22222222")]:
            index.append({"texture_name":"icon_poke_0025_00_00_00",
                          "texinfo_hash":tex,"g1t_hash":g1t,
                          "texture_number_candidate":"0025","category":"pokemon",
                          "texinfo_filename":tex+".texinfo","g1t_filename":g1t+".g1t",
                          "texinfo_record_index":"0","texture_layer":"0",
                          "native_source_kind":"ORIGINAL_NATIVE_G1T",
                          "status":"PHYSICAL_G1T_PRESENT"})
            sources.append({"texture_name":"icon_poke_0025_00_00_00",
                            "texinfo_hash":tex,"g1t_hash":g1t,
                            "png_path":tex+".png","png_sha256":"a"*64,
                            "swizzle_layout":"ounce8","status":"PNG_CANDIDATE_UNVERIFIED"})
        edges = [{"texinfo_hash":"aaaa1234","g1t_hash":"11111111",
                  "object_hash":"abcdefab","objdb_file":"a.kidsobjdb"},
                 {"texinfo_hash":"bbbb1234","g1t_hash":"22222222",
                  "object_hash":"12345678","objdb_file":"b.kidsobjdb"}]
        out = build(index,sources,edges)
        self.assertEqual(len(out),2)
        self.assertEqual(len({row["png_path"] for row in out}),2)
        self.assertTrue(all(x["native_species_id_verified"]=="" for x in out))
        ambiguous = build(index,sources,edges+edges[:1])
        self.assertEqual(ambiguous[0]["link_status"],"MISSING_OR_AMBIGUOUS_KIDSOBJDB_INDEX_EDGE")
        self.assertEqual(ambiguous[1]["link_status"],"INDEX_PNG_AND_HASH_EDGE_LINKED")


if __name__=="__main__":
    unittest.main()
