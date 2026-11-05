"""M9.15 tests: source register survives; owner+0x28 not generic BLR."""
import struct
import unittest
from unittest.mock import patch

from Scripts.resources.m9_owner_object_escape import (
    ldrx,is_blr_reg,find_owner_field_reads,owner_escape
)


def ldr(rn,rd,byte_offset):
    return 0xf9400000 | ((byte_offset//8)<<10) | (rn<<5) | rd


class NativeObjectOwnerTests(unittest.TestCase):
    def test_precise_ldr_and_blr(self):
        self.assertEqual(ldrx(ldr(19,23,0x28)),{"base":19,"dst":23,"offset":0x28})
        self.assertIsNone(ldrx(0xd503201f))
        self.assertTrue(is_blr_reg(0xd63f0100,8))
        self.assertFalse(is_blr_reg(0xd63f0100,9))

    def test_direct_owner_read_to_vtable_dispatch_still_untyped(self):
        words=[
            ldr(19,23,0x28),ldr(23,8,0),ldr(8,8,0x38),0xd63f0100,
            *([0xd503201f]*20),
        ]
        code=struct.pack("<"+"I"*len(words),*words)
        got=find_owner_field_reads(code,base=0x1000)
        self.assertEqual(got["all_native_ldr_from_owner_plus_0x28"],1)
        self.assertEqual(got["owner_member_plus_callback_pattern_candidates"],1)
        self.assertEqual(got["four_instruction_exact_patterns"],1)
        row=got["pattern_examples"][0]
        self.assertFalse(row["owner_class_identity_verified"])
        self.assertFalse(row["descriptor_callback_target_verified"])
        self.assertFalse(row["script_text_fk_verified"])

    def test_wrong_owner_offset_does_not_count(self):
        words=[ldr(19,23,0x20),ldr(23,8,0),ldr(8,8,0x38),0xd63f0100]+[0xd503201f]*20
        got=find_owner_field_reads(struct.pack("<"+"I"*len(words),*words),0x1000)
        self.assertEqual(got["all_native_ldr_from_owner_plus_0x28"],0)

    def test_strict_prior_vptr_evidence_gate(self):
        prior={"report":{"original_exefs_sha256":"fake"},"verified_stores":[]}
        with self.assertRaises(ValueError):
            owner_escape(b"\0"*100,0,prior)


if __name__=="__main__":
    unittest.main()
