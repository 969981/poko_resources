"""Original typed KIDSOBJDB texture-hash source tests."""
import struct,unittest
from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids,G1T,TEXINFO,UNKNOWN

def fixture():
    fields=[(5,1,G1T,0xd58f20b8),(5,1,TEXINFO,0x00de13ed),(5,1,UNKNOWN,0)]
    record=bytearray(b"IDOK0000"+struct.pack("<IIII",72,0x6d6b6d87,0x79991e79,3))
    for kind,count,name,_ in fields:record+=struct.pack("<III",kind,count,name)
    for _,_,_,value in fields:record+=struct.pack("<I",value)
    return b"_DOK0000"+struct.pack("<IIIII",28,24,1,0x9ff4c728,28+len(record))+record

class NativeKidsTextureTests(unittest.TestCase):
    def test_native_property_offsets(self):
        meta,nodes=parse_kids(fixture())
        self.assertEqual(meta["nodes"],1)
        self.assertEqual(meta["name_resource_hash"],"9ff4c728")
        obj=nodes[0x6d6b6d87]
        self.assertEqual(obj["offset"],28)
        self.assertEqual(obj["fields"][G1T]["u32"],0xd58f20b8)
        self.assertEqual(obj["fields"][TEXINFO]["u32"],0x00de13ed)
        self.assertEqual(obj["fields"][UNKNOWN]["u32"],0)
    def test_bad_original_source_rejected(self):
        with self.assertRaisesRegex(ValueError,"header/size"):parse_kids(fixture()[:-1])
        corrupted=bytearray(fixture());corrupted[28:36]=b"BADK0000"
        with self.assertRaisesRegex(ValueError,"IDOK"):parse_kids(bytes(corrupted))

if __name__=="__main__":unittest.main()
