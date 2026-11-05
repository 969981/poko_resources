"""M9.7: target-address xrefs are not runtime descriptor readers."""
import struct
import unittest

from Scripts.resources.m9_descriptor_reader_trace import (
    branch_target, scan_text, scan_u64_literals,
)


class DescriptorEntryXrefTests(unittest.TestCase):
    def test_arm64_bl_and_tail_branch_signed_offsets(self):
        pc = 0x3000
        self.assertEqual(branch_target(0x94000004, pc), ("BL_DIRECT", pc + 16))
        self.assertEqual(branch_target(0x17fffffc, pc), ("B_DIRECT", pc - 16))
        self.assertIsNone(branch_target(0xd65f03c0, pc))

    def test_direct_call_and_adrp_add_are_distinct(self):
        name = "0x12345678"
        target = 0x2340
        base = 0x1000
        adrp_x0_page_2000 = 0xb0000000
        add_x0_340 = 0x91000000 | (0x340 << 10)
        call_pc = base + 8
        bl_target = 0x94000000 | ((target - call_pc) >> 2)
        code = struct.pack("<III", adrp_x0_page_2000, add_x0_340, bl_target)
        hits = scan_text(code, base, {name: target})
        self.assertEqual({x["kind"] for x in hits},
                         {"ADRP_ADD_ADDRESS_CANDIDATE", "BL_DIRECT"})
        self.assertTrue(all(not h["runtime_reader_verified"] for h in hits))
        self.assertTrue(all(not h["text_fk_verified"] for h in hits))

    def test_data_pointer_is_not_getter(self):
        key = "0x12345678"
        target = 0x2340
        sections = [
            {"name": "text", "mem_offset": 0, "data": struct.pack("<Q", target)},
            {"name": "rodata", "mem_offset": 0x3000,
             "data": b"\0" * 8 + struct.pack("<Q", target)},
        ]
        hits = scan_u64_literals(sections, {key: target})
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["site_pc"], 0x3008)
        self.assertEqual(hits[0]["kind"], "U64_LITERAL_ADDRESS_CANDIDATE")
        self.assertFalse(hits[0]["runtime_reader_verified"])


if __name__ == "__main__":
    unittest.main()
