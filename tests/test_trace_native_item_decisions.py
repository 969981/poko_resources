"""M11.2: raw byte reads reaching ARM64 conditional consumers, not fake enums."""
import struct
import unittest

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from Scripts.resources.trace_native_item_decisions import scan_user
from Scripts.resources.trace_native_item_provenance import field_load

def data(*words):
    return b"".join(struct.pack("<I",w) for w in words)

def ldrb(base, dest, displacement):
    return 0x39400000 | (displacement<<10) | (base<<5) | dest

def cmpw(reg, immediate):
    return 0x7100001f | (immediate<<10) | (reg<<5)

def strb(base, source, displacement):
    return 0x39000000 | (displacement<<10) | (base<<5) | source

class DecisionsTests(unittest.TestCase):
    def setUp(self):
        self.md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
        self.md.detail=True

    def events(self,*words):
        code=data(*words)
        site={"pc":0x1000, **field_load(words[0])}
        return scan_user(self.md,code,0x1000,site)

    def test_real_direct_enum_comparison_without_false_semantics(self):
        events=self.events(ldrb(19,5,0x26),cmpw(5,16),0xd65f03c0)
        self.assertEqual(len(events),1)
        self.assertEqual(events[0]["kind"],"RAW_FIELD_REGISTER_USED_IN_CONDITION")
        self.assertEqual(events[0]["immediate"],16)

    def test_different_register_compare_not_counted(self):
        self.assertEqual(self.events(ldrb(19,5,0x26),cmpw(6,16),
                                     0xd65f03c0),[])

    def test_conditional_after_written_register_not_counted(self):
        self.assertEqual(self.events(ldrb(19,5,0x26),0x52800025,
                                     cmpw(5,16),0xd65f03c0),[])

    def test_branch_before_compare_not_counted(self):
        self.assertEqual(self.events(ldrb(19,5,0x26),0x14000001,
                                     cmpw(5,16),0xd65f03c0),[])

    def test_copy_survey_does_not_equal_enum_consumer(self):
        events=self.events(ldrb(19,5,0x26),strb(20,5,0x26),0xd65f03c0)
        self.assertEqual([x["kind"] for x in events],["IMMEDIATE_RAW_FIELD_STORE"])

if __name__=="__main__":
    unittest.main()
