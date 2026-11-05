"""M9.12: native ADD dataflow and vptr+offset function-pointer tests."""
import struct
import unittest
from Scripts.resources.m9_verified_vptr_assignments import reconstruct_address,read_pointer,verify_one

def adrp(pc,page,rd=8):
    imm=((page-(pc&~0xfff))>>12)&0x1fffff
    return 0x90000000|((imm&3)<<29)|((imm>>2)<<5)|rd

def add(rd,rn,n):
    return 0x91000000|(n<<10)|(rn<<5)|rd

STP_X8_XZR_AT_X23=0xa9007ee8


class VptrFlowTests(unittest.TestCase):
    def test_vptr_x8_flow_and_callback_slot(self):
        base=0x1000
        page=0x3000
        words=[adrp(base,page),add(8,8,0x40),add(8,8,0x10),STP_X8_XZR_AT_X23]
        code=struct.pack("<4I",*words)
        p={"adrp_pc":base,"add_pc":base+4,"final_add_pc":base+8,"store_pc":base+12,
           "source_object_reg":"x23","vptr":0x3050,"descriptor_slot":0x3088,
           "callback":0x1234,"hash":"0xf92c5190","id":"test"}
        self.assertEqual(reconstruct_address(code,base,p),0x3050)
        data=bytearray(0x200)
        struct.pack_into("<Q",data,0x88,0x1234)
        section={"name":"data","mem_offset":page,"data":bytes(data)}
        self.assertEqual(read_pointer(section,0x3088),0x1234)
        doc={"sites":[{"adrp_pc":base,"address_pc":base+4,
                       "adrp_add_bytes_confirmed":True}]}
        actual=verify_one(code,base,section,p,doc)
        self.assertTrue(actual["verified_original_arm64_vptr_assignment"])
        self.assertTrue(actual["verified_callback_pointer_at_vptr_offset"])
        self.assertEqual(actual["vtable_callback_offset"],0x38)
        self.assertFalse(actual["verified_runtime_indirect_dispatch"])
        self.assertFalse(actual["verified_script_text_fk"])

    def test_x8_clobber_or_wrong_slot_fails_closed(self):
        base=0x1000
        words=[adrp(base,0x3000),add(8,8,0x40),add(9,8,0x10),STP_X8_XZR_AT_X23]
        code=struct.pack("<4I",*words)
        chain={"adrp_pc":base,"add_pc":base+4,"final_add_pc":base+8}
        with self.assertRaises(ValueError):
            reconstruct_address(code,base,chain)
        section={"name":"data","mem_offset":0x3000,"data":bytes(0x100)}
        with self.assertRaises(ValueError):
            read_pointer(section,0x3500)

if __name__=="__main__":
    unittest.main()
