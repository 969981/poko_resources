"""M11.3: exact ADRP/BL/STR source bytes, false resource identity avoidance."""
import struct
import unittest
from Scripts.resources.trace_native_item_resource_loader import (
    adrp_target, bl_target, mem_x, chain, find_xrefs, FIRST, SECOND, PAGE, DISP
)

def adrp(pc,dest,target):
    delta=(target-(pc&~0xfff))//4096
    delta&=(1<<21)-1
    return 0x90000000 | ((delta&3)<<29) | ((delta>>2)<<5) | dest

def bl(pc,target):
    return 0x94000000 | (((target-pc)//4)&0x3ffffff)

def assemble(*words):
    return b"".join(struct.pack("<I",w) for w in words)

class LoaderTests(unittest.TestCase):
    def test_direct_983_two_calls_and_global_store(self):
        pc=0x1000
        words=[
          0x52800000 | (983<<5),bl(pc+4,FIRST),
          bl(pc+8,SECOND),adrp(pc+12,8,PAGE),
          0xf9000000 | ((DISP//8)<<10) | (8<<5)
        ]
        result=chain(assemble(*words),pc,pc)
        self.assertEqual(result["global_rva"],hex(PAGE+DISP))
        self.assertEqual(result["grade"],
                         "DIRECT_INSTRUCTION_CHAIN_VERIFIED__TABLE_SEMANTICS_UNPROVEN")

    def test_wrong_literal_and_wrong_store_do_not_count(self):
        pc=0x1000
        code=assemble(0x52800000 | (982<<5),bl(pc+4,FIRST),
                      bl(pc+8,SECOND),adrp(pc+12,8,PAGE),
                      0xf9000000 | ((DISP//8)<<10) | (8<<5))
        with self.assertRaisesRegex(ValueError,"CHAIN_DID_NOT_MATCH"):
            chain(code,pc,pc)

    def test_register_page_read_matching(self):
        pc=0x1000
        code=assemble(adrp(pc,8,PAGE),
                      0xf9400000 | ((DISP//8)<<10) | (8<<5) | 3,
                      0xd65f03c0)
        self.assertEqual(adrp_target(struct.unpack_from("<I",code)[0],pc),PAGE)
        self.assertEqual(find_xrefs(code,pc)[0]["operation"],"ldr")

    def test_negative_page_and_out_of_bounds(self):
        self.assertIsNone(bl_target(0xd503201f,0x1000))
        self.assertIsNone(mem_x(0xd65f03c0,True))
        with self.assertRaises(ValueError):
            chain(bytes(4),0,0x1000)

if __name__=="__main__": unittest.main()
