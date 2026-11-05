"""M9.10 strict-pointer provenance and conservative ARM64 xref tests."""
import struct
import unittest
from Scripts.resources.m9_vtable_neighborhood import scan_neighborhood, pointer_slots

def adrp(pc, target_page, rd=1):
    page_delta=(target_page-(pc&~0xfff))//4096
    imm=page_delta&0x1fffff
    return 0x90000000|((imm&3)<<29)|((imm>>2)<<5)|rd

def add_imm(rn, rd, imm):
    return 0x91000000|(imm<<10)|(rn<<5)|rd

class NativeVtableTests(unittest.TestCase):
    def test_nearby_address_point_not_exact_slot(self):
        base=0x1000
        code=struct.pack("<II",adrp(base,0x3000),add_imm(1,0,0x10))
        rows=scan_neighborhood(code,base,{"hash":(0x3018,0x2000)},window=0x80)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["delta_from_slot"],-8)
        self.assertEqual(rows[0]["evidence_grade"],"ADJACENT_ARM64_ADDRESS_CONSTRUCTION")
        self.assertFalse(rows[0]["vtable_address_point_confirmed"])
        self.assertFalse(rows[0]["indirect_runtime_call_confirmed"])
        self.assertFalse(rows[0]["script_text_fk_confirmed"])

    def test_outside_window_excluded(self):
        base=0x1000
        code=struct.pack("<II",adrp(base,0x3000),add_imm(1,0,0x500))
        self.assertEqual(scan_neighborhood(code,base,{"hash":(0x3018,0x2000)},window=0x80),[])

    def test_nonadjacent_can_only_be_candidate(self):
        base=0x1000
        code=struct.pack("<III",adrp(base,0x3000),0xd503201f,add_imm(1,0,0x18))
        rows=scan_neighborhood(code,base,{"hash":(0x3018,0x2000)},window=0x80)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["evidence_grade"],"NONADJACENT_ARM64_ADDRESS_CANDIDATE")

    def test_previous_evidence_fingerprint_required(self):
        with self.assertRaises(ValueError):
            pointer_slots({"report":{"source_exefs_sha256":"incorrect","static_pointer_slots":[]}})

if __name__=="__main__":
    unittest.main()
