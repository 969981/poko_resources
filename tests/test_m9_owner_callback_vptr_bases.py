"""M9.19: only original table-derived vptr base hypothesis is accepted."""
import struct
import unittest

from Scripts.resources.m9_owner_callback_vptr_bases import (
    KNOWN,derived_base_candidates,scan_specific_adrp,
)


def adr_page(pc,target,rd=8):
    imm=((target-(pc&~0xfff))>>12)&0x1fffff
    return 0x90000000|((imm&3)<<29)|((imm>>2)<<5)|rd


def add_reg(rn,rd,imm):
    return 0x91000000|(imm<<10)|(rn<<5)|rd


class FocusedCallbackBaseTests(unittest.TestCase):
    def test_two_original_function_slots_derive_only_hypotheses(self):
        base=0x32fde00
        data=bytearray(0x180)
        struct.pack_into("<Q",data,0x00,0x11111)
        struct.pack_into("<Q",data,0x38,KNOWN["owner_cleanup_callback"][1])
        struct.pack_into("<Q",data,0x100,0x22222)
        struct.pack_into("<Q",data,0x138,KNOWN["owner_constructor_callback"][1])
        guesses=derived_base_candidates({"mem_offset":base,"data":bytes(data)})
        self.assertEqual([g["hypothesized_vptr"] for g in guesses],
                         [0x32fde00,0x32fdf00])
        self.assertTrue(all(g["callback_at_derived_vptr_plus_0x38_exact"] for g in guesses))
        self.assertTrue(all(not g["proven_vptr"] for g in guesses))

    def test_targeted_adrp_add_does_not_establish_vptr_store(self):
        base=0x1000
        code=struct.pack("<III",adr_page(base,0x3000),add_reg(8,8,0x50),0xd503201f)
        rows,counts=scan_specific_adrp(code,base,{0x3050,0x3060})
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["constructed_data_va"],0x3050)
        self.assertFalse(rows[0]["object_vptr_store_verified"])
        self.assertEqual(counts[0x3050],1)

    def test_nonmatching_target_ignored(self):
        base=0x1000
        code=struct.pack("<II",adr_page(base,0x3000),add_reg(8,8,0x50))
        rows,counts=scan_specific_adrp(code,base,{0x30a0})
        self.assertEqual(rows,[])
        self.assertEqual(counts,{})


if __name__=="__main__":unittest.main()
