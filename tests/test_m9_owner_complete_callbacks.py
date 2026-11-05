"""M9.21: computed BR must not truncate original exact callback method."""
import struct
import unittest

from Scripts.resources.m9_owner_complete_callbacks import inspect_function,code_edges


def ldr(rn,rd,offset):
    return 0xf9400000|((offset//8)<<10)|(rn<<5)|rd


class CompleteOwnerCallbackTests(unittest.TestCase):
    def test_jump_table_br_followed_by_owner_member_read(self):
        base=0x1000
        words=[
            0xaa0303f3,    # mov x19,x3
            0xd61f0120,    # br x9: computed indirect jump
            0xd503201f,    # nop
            ldr(19,22,0x28),
            ldr(22,1,8),
            0xd65f03c0,
        ]
        code=struct.pack("<"+"I"*len(words),*words)
        d=inspect_function("test",code,base,base,base+len(code))
        self.assertEqual(len(d["owner_plus_0x28_reads"]),1)
        self.assertTrue(d["owner_plus_0x28_reads"][0]["preceding_x3_to_x19_alias"])
        self.assertEqual(d["computed_jump_table_br_count"],1)
        self.assertFalse(d["runtime_object_identity_proven"])
        self.assertFalse(d["M7_text_fk_proven"])

    def test_direct_branch_is_structural_edge_not_runtime_proof(self):
        ins=[
            {"pc":0x1000,"mnemonic":"b","operands":"#0x1010"},
            {"pc":0x1004,"mnemonic":"br","operands":"x9"},
            {"pc":0x1008,"mnemonic":"ret","operands":""},
        ]
        edges=code_edges(ins,0x1000,0x1020)
        self.assertEqual(len(edges),2)
        self.assertTrue(edges[0]["target_in_current_method"])
        self.assertFalse(edges[1]["resolved"])


if __name__=="__main__":unittest.main()
