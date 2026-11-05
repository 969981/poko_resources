"""M9.11: exact ARM64 source words and context are required."""
import struct
import unittest
from Scripts.resources.m9_vptr_constructor_windows import inspect_site


def encode_adrp(pc, page, rd=8):
    n=((page-(pc&~0xfff))>>12)&0x1fffff
    return 0x90000000|((n&3)<<29)|((n>>2)<<5)|rd

def encode_add(rn,rd,imm):
    return 0x91000000|(imm<<10)|(rn<<5)|rd


class VptrInstructionProvenanceTests(unittest.TestCase):
    def test_exact_address_but_no_unearned_vptr_ownership(self):
        base=0x1000
        first=encode_adrp(base,0x3000)
        second=encode_add(8,8,0x90)
        code=struct.pack("<IIII",first,second,0xd503201f,0xd65f03c0)
        rec={
            "property_hash":"0xf92c5190","adrp_pc":base,"consumer_pc":base+4,
            "address_point":0x3090,"instruction_kind":"ADRP_ADD_ADDRESS",
            "adrp_word":f"{first:08x}","consumer_word":f"{second:08x}",
        }
        section={"name":"data","mem_offset":0x3000,"data":bytes(256)}
        observed=inspect_site(code,base,section,rec)
        self.assertTrue(observed["adrp_add_bytes_confirmed"])
        self.assertEqual(observed["address_point"],0x3090)
        self.assertFalse(observed["verified_vptr_store"])
        self.assertFalse(observed["verified_text_fk"])
        self.assertTrue(len(observed["instruction_window"])>=2)
        rec["consumer_word"]="ffffffff"
        with self.assertRaises(ValueError):
            inspect_site(code,base,section,rec)

    def test_invalid_address_projection_rejected(self):
        base=0x1000
        first=encode_adrp(base,0x3000)
        second=encode_add(8,8,0x90)
        code=struct.pack("<II",first,second)
        rec={
            "property_hash":"key","adrp_pc":base,"consumer_pc":base+4,
            "address_point":0x3010,"instruction_kind":"ADRP_ADD_ADDRESS",
            "adrp_word":f"{first:08x}","consumer_word":f"{second:08x}",
        }
        with self.assertRaises(ValueError):
            inspect_site(code,base,{"name":"data","mem_offset":0x3000,"data":bytes(256)},rec)


if __name__=="__main__":
    unittest.main()
