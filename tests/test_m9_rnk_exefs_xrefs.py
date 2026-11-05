"""M9.4 raw ARM64 ADRP/LDR/ADD hash-load xref regression."""
import struct
import unittest
from Scripts.resources.m9_rnk_exefs_xrefs import decode_adrp,decode_load,decode_add,find_references

def adrp(rd,delta_pages):
    imm=(delta_pages&((1<<21)-1))
    return 0x90000000 | ((imm&3)<<29) | (((imm>>2)&0x7ffff)<<5) | rd
def ldr_w(rd,rn,disp):
    assert disp%4==0
    return 0xb9400000 | ((disp//4)<<10) | (rn<<5) | rd
def add_x(rd,rn,disp):
    return 0x91000000 | ((disp&0xfff)<<10) | (rn<<5) | rd

class Arm64ReferenceTests(unittest.TestCase):
    def test_adrp_decoder_signed_and_unsigned_pages(self):
        self.assertEqual(decode_adrp(adrp(3,2),0),(8192,3))
        self.assertEqual(decode_adrp(adrp(1,-1),0x2000),(0x1000,1))
    def test_adjacent_adrp_ldr_w_targets_exact_hash_value(self):
        code=struct.pack("<II",adrp(3,2),ldr_w(1,3,12))
        rows=find_references(code,0,{0x200c:0xA91711C6})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["literal_virtual_offset"],0x200c)
        self.assertEqual(rows[0]["instruction_kind"],"LDR_W")
        self.assertEqual(rows[0]["evidence"],"DIRECT_ADJACENT_ARM64_LITERAL_ACCESS")
        self.assertEqual(rows[0]["property_consumer_verified"],0)
    def test_nearby_add_only_candidate_not_consumption_proof(self):
        code=struct.pack("<III",adrp(3,2),0xd503201f,add_x(4,3,12))
        rows=find_references(code,0,{0x200c:0xA91711C6})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["instruction_kind"],"ADD_ADDRESS")
        self.assertEqual(rows[0]["evidence"],"NONADJACENT_AARCH64_POSSIBLE_ACCESS")
        self.assertEqual(rows[0]["property_consumer_verified"],0)
    def test_no_wrong_adrp_base_register_match(self):
        code=struct.pack("<II",adrp(3,2),ldr_w(1,2,12))
        self.assertEqual(find_references(code,0,{0x200c:1}),[])
    def test_no_random_32bit_constant_marked_as_adrp(self):
        self.assertIsNone(decode_adrp(0xA91711C6,0))
        self.assertIsNone(decode_add(0xA91711C6))
        self.assertIsNone(decode_load(0xA91711C6))

if __name__=="__main__":unittest.main()
