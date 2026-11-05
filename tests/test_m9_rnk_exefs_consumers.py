"""M9.3 AArch64 immediate probes stay unverified consumers."""
import struct
import unittest
from Scripts.resources.m9_rnk_exefs_consumers import immediate_pairs, select_hashes

def movz(reg,half):
    return 0x52800000 | ((half&0xFFFF)<<5) | reg
def movk(reg,half):
    return 0x72800000 | (1<<21) | ((half&0xFFFF)<<5) | reg

class ExefsHashProbeTests(unittest.TestCase):
    def test_arm64_movz_movk_reconstructs_hash_but_not_caller(self):
        target=0xA91711C6
        code=struct.pack("<III",movz(3,target&0xFFFF),0xD503201F,
                         movk(3,target>>16))
        result=immediate_pairs(code,0x1000,{target})
        self.assertEqual(len(result[target]),1)
        self.assertEqual(result[target][0]["text_va_movz"],0x1000)
        self.assertEqual(result[target][0]["text_va_movk"],0x1008)
        self.assertEqual(result[target][0]["status"],"ARM64_IMMEDIATE_PAIR_NO_DATAFLOW")
    def test_far_movk_does_not_claim_pair(self):
        target=0xA91711C6
        code=struct.pack("<I",movz(3,target&0xFFFF))+b"\x1f\x20\x03\xd5"*15+struct.pack("<I",movk(3,target>>16))
        self.assertEqual(dict(immediate_pairs(code,0,{target})),{})
    def test_hashes_are_sourced_from_native_histogram_and_namefile(self):
        summary={"files":[{"candidate_property_hash_histogram":
            {"0x11112222":10,"0xABCD1234":20}}]}
        owners={"source_name_hashes":{"root:1":"a91711c6"}}
        hashes,count=select_hashes(summary,owners)
        self.assertEqual(set(hashes),{0x11112222,0xABCD1234,0xA91711C6})
        self.assertEqual(count[0xABCD1234],20)

if __name__=="__main__":unittest.main()
