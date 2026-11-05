"""M20 tests: original descriptor address ranges and global pointer false positives."""
import struct
import unittest
from Scripts.resources.m20_item983_cache_provenance import (
    section_read, inspect_descriptor, descriptor_survey,
    all_bl_callers, exact_global_xrefs, find_unqualified_global_displacements,
    analyze, PAGE, DISP, TABLE_BASE, TABLE_STRIDE
)

def adrp(pc,rd,target):
    delta=((target&~0xfff)-(pc&~0xfff))//0x1000
    if not -(1<<20) <= delta < (1<<20):
        raise ValueError("ADRP_TEST_TOO_FAR")
    code=delta&0x1fffff
    return 0x90000000|((code&3)<<29)|(((code>>2)&0x7ffff)<<5)|rd

def ins(*words):
    return b"".join(struct.pack("<I",w) for w in words)

def ldr64(rn,rt,disp):
    return 0xf9400000|((disp//8)<<10)|(rn<<5)|rt

def str64(rn,rt,disp):
    return 0xf9000000|((disp//8)<<10)|(rn<<5)|rt

def bl(pc,dest):
    assert (dest-pc)%4 == 0
    return 0x94000000|(((dest-pc)//4)&0x3ffffff)

class M20Tests(unittest.TestCase):
    def test_descriptor_raw_bytes_addressed_by_index(self):
        p={"mem_offset":TABLE_BASE,"data":bytes(TABLE_STRIDE*0x4ab),"name":"rodata"}
        s=inspect_descriptor([p],983)
        self.assertEqual(s["descriptor_rva"],hex(TABLE_BASE+983*0x28))
        self.assertEqual(s["section"],"rodata")
        self.assertEqual(len(s["original_40_bytes_hex"]),80)
        self.assertEqual(descriptor_survey([p])["descriptor_count_if_zero_based"],1195)
        with self.assertRaisesRegex(ValueError,"OUT_OF_BOUNDS"):
            inspect_descriptor([p],1195)

    def test_direct_and_add_alias_global_read_write(self):
        base=0x1000
        code=ins(
            adrp(base,8,PAGE),
            ldr64(8,9,DISP),
            str64(8,0,DISP),
            0xd65f03c0,
            adrp(base+16,11,PAGE),
            0x91000000 | (DISP<<10) | (11<<5) | 12,
            ldr64(12,10,0),
            0xd65f03c0
        )
        result=exact_global_xrefs(code,base)
        self.assertEqual(result["exact_direct_load_store_site_count"],3)
        self.assertEqual(
            [x["kind"] for x in result["direct_sites"]],
            ["direct_memory_read","direct_memory_write","direct_memory_read"])
        self.assertEqual(find_unqualified_global_displacements(code,base)["raw_offset_hits_unqualified"],2)

    def test_wrong_page_not_a_global_hit(self):
        base=0x1000
        code=ins(adrp(base,8,PAGE+0x1000),ldr64(8,9,DISP),0xd65f03c0)
        self.assertEqual(exact_global_xrefs(code,base)["exact_direct_load_store_site_count"],0)
        self.assertEqual(find_unqualified_global_displacements(code,base)["raw_offset_hits_unqualified"],1)

    def test_direct_call_is_not_an_indirect_call(self):
        base=0x2000
        code=ins(bl(base,0x4000),0xd63f0100,0xd65f03c0)
        calls=all_bl_callers(code,base,{0x4000,0x5000})
        self.assertEqual(calls["0x4000"]["first_pcs"],["0x2000"])
        self.assertEqual(calls["0x5000"]["direct_bl_count"],0)

    def test_sha_lock_rejects_fake_original(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_SHA_MISMATCH"):
            analyze(b"invalid",b"invalid")

if __name__=="__main__":
    unittest.main()
