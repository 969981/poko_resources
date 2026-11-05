"""Native typed object-ID matches remain candidates, not species-ID proof."""
import struct,tempfile,unittest
from pathlib import Path
from Scripts.resources.m17_pokemon_object_backrefs import candidates

def db_with_reference(target):
    # A completely separate source object has one typed 32-bit member
    # referencing the target OID. Distinct from the target layout object.
    row=(b"IDOK0000"+
         struct.pack("<IIII",52,0x11223344,0xaabbccdd,1)+
         struct.pack("<III",5,1,0x12345678)+struct.pack("<I",target))
    return b"_DOK0000"+struct.pack("<IIIII",28,24,1,0x87654321,28+len(row))+row

class OidReverseReferenceTests(unittest.TestCase):
    def test_proven_typed_u32_value_but_not_species_identity(self):
        oid=0x6d6b6d87
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"root_000001_abcdef01.kidsobjdb"
            path.write_bytes(db_with_reference(oid))
            hits,summary=candidates([path],{oid:["icon_poke_0082_00_00_00"]})
        self.assertEqual(len(hits),1)
        self.assertEqual(summary["unique_target_icon_oids_referenced"],1)
        self.assertEqual(summary["native_species_id_binding_verified"],0)
        self.assertEqual(hits[0]["native_property_hash"],"12345678")
        self.assertEqual(hits[0]["proven_species_id_binding"],0)
        self.assertIn("icon_poke_0082",hits[0]["matched_target_sprites"])

    def test_native_size_failure_reported_not_pretended_success(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"bad.kidsobjdb"
            path.write_bytes(db_with_reference(9)[:-1])
            hits,summary=candidates([path],{9:["icon_poke_0009_00_00_00"]})
        self.assertEqual(hits,[])
        self.assertEqual(summary["source_parse_status"]["PARSE_FAILED"],1)

if __name__=="__main__":unittest.main()
