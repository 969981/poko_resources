"""NSO0 original section boundaries and string-reference survey safety."""
import struct
import unittest
from Scripts.resources.trace_native_species_item_callers import get_sections,scan_strings


def fixture():
    text=b"\x1f\x20\x03\xd5"*4
    ro=b"icon_poke_uni_%04d\x00item_type_material\x00ordinary\x00"
    data=b"native\x00"
    buf=bytearray(0x100+len(text)+len(ro)+len(data))
    buf[:4]=b"NSO0"
    struct.pack_into("<I",buf,0x0c,0)
    struct.pack_into("<III",buf,0x10,0x100,0,len(text))
    struct.pack_into("<III",buf,0x20,0x100+len(text),0x5000,len(ro))
    struct.pack_into("<III",buf,0x30,0x100+len(text)+len(ro),0x8000,len(data))
    buf[0x100:0x100+len(text)]=text
    buf[0x100+len(text):0x100+len(text)+len(ro)]=ro
    buf[0x100+len(text)+len(ro):]=data
    return bytes(buf)


class NsoReferenceTests(unittest.TestCase):
    def test_native_nso_rodata_has_exact_unnormalized_virtual_offsets(self):
        kind,segments=get_sections(fixture())
        self.assertEqual(kind,"NSO0")
        self.assertEqual(len(segments),3)
        self.assertEqual(segments[1]["name"],"rodata")
        self.assertEqual(segments[1]["mem_offset"],0x5000)
        rows=scan_strings(segments)
        self.assertEqual(rows[0]["text"],"icon_poke_uni_%04d")
        self.assertEqual(rows[0]["virtual_offset"],0x5000)
        self.assertEqual(rows[0]["target_group"],"POKEMON_ICON")
        self.assertEqual(rows[1]["target_group"],"MATERIAL_CRAFT_REFERENCE")

    def test_corrupt_segment_bounds_rejected(self):
        raw=bytearray(fixture())
        struct.pack_into("<I",raw,0x28,0x7fffffff)
        with self.assertRaisesRegex(ValueError,"section bounds"):
            get_sections(bytes(raw))
        with self.assertRaisesRegex(ValueError,"NSO field"):
            get_sections(b"NSO0")


if __name__=="__main__":
    unittest.main()
