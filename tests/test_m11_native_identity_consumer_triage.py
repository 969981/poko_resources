"""M11 keeps native item pointer register matches separated from semantic proof."""
import struct
import unittest
from Scripts.resources.m11_native_identity_consumer_triage import (
    classify_load_candidates,load_at,imm_at
)

class NativeIdentityTriageTests(unittest.TestCase):
    def test_same_base_name_index_and_group_byte_are_ranked(self):
        # Synthetic ARM64, real on-disk native item field offsets.
        words=[0xd503201f]*128
        base_reg=3
        words[30]=0x52800000|(4600<<5)
        words[35]=0x52800000|(68<<5)
        words[40]=0x79400000|((0x22//2)<<10)|(base_reg<<5)|4
        words[42]=0x39400000|(0x26<<10)|(base_reg<<5)|5
        words[44]=0x39400000|(0x3a<<10)|(base_reg<<5)|6
        code=b"".join(struct.pack("<I",x) for x in words)
        report=classify_load_candidates(code,0x123000)
        self.assertEqual(report["total_load_0x26"],1)
        self.assertEqual(report["ranked_candidates"],1)
        hit=report["top"][0]
        self.assertEqual(hit["base_register"],"x3")
        self.assertTrue(hit["candidate_score"]>=20)
        self.assertFalse(hit["native_item_base_verified"])
        self.assertIn(34,[x["offset"] for x in hit["same_base_loads"]])
        self.assertEqual(load_at(words[42])[:2],("ldrb",38))
        self.assertEqual(imm_at(words[35]),68)

    def test_random_offset_does_not_elevate_item_semantics(self):
        word=0x39400000|(0x26<<10)|(7<<5)|8
        code=b"".join(struct.pack("<I",x) for x in (0xd503201f,word,0xd503201f))
        r=classify_load_candidates(code,0)
        self.assertEqual(r["total_load_0x26"],1)
        self.assertEqual(r["ranked_candidates"],0)

if __name__=="__main__":
    unittest.main()
