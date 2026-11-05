"""M9.14: generic virtual call shape must not imply callback identity."""
import struct
import unittest

from Scripts.resources.m9_vptr_dispatch_slot38 import ldr64,branch_indirect,scan_dispatch_patterns


def ldr(base,dest,offset):
    return 0xf9400000|((offset//8)<<10)|(base<<5)|dest


class DispatchShapeTests(unittest.TestCase):
    def test_adjacent_ldr_vptr_ldr_slot_blr_only_generic(self):
        instructions=[ldr(0,8,0),ldr(8,8,0x38),0xd63f0100]+[0xd503201f]*10
        stats,examples=scan_dispatch_patterns(struct.pack("<"+"I"*len(instructions),*instructions),0x1000)
        self.assertEqual(stats["ADJACENT_LDR_VPTR_LDR_SLOT_BLR_SHAPE"],1)
        self.assertEqual(examples[0]["slot_load_pc"],0x1004)
        self.assertFalse(examples[0]["target_class_or_vtable_proven"])
        self.assertFalse(examples[0]["specific_descriptor_callback_proven"])
        self.assertFalse(examples[0]["script_text_fk_verified"])

    def test_wrong_slot_or_callback_register_not_matched(self):
        instructions=[ldr(0,8,0),ldr(8,8,0x30),0xd63f0100]+[0xd503201f]*10
        stats,examples=scan_dispatch_patterns(struct.pack("<"+"I"*len(instructions),*instructions),0x1000)
        self.assertEqual(examples,[])
        self.assertEqual(stats.get("all_ldr64_slot_0x38",0),0)
        self.assertEqual(ldr64(ldr(8,8,0x30))[2],0x30)
        self.assertEqual(branch_indirect(0xd63f0100),("BLR",8))

    def test_nonmatching_indirect_branch_reg_filtered(self):
        instructions=[ldr(0,8,0),ldr(8,8,0x38),0xd63f0120]+[0xd503201f]*10
        stats,examples=scan_dispatch_patterns(struct.pack("<"+"I"*len(instructions),*instructions),0x1000)
        self.assertEqual(examples,[])
        self.assertEqual(stats["all_ldr64_slot_0x38"],1)

if __name__=="__main__":
    unittest.main()
