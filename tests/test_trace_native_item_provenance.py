"""M11 native ARM64 register-provenance: opcode, branch and kill negative controls."""
import struct
import unittest

from Scripts.resources.trace_native_item_provenance import (
    field_load, cmp_immediate, movz_immediate, scan, evaluate,
    no_register_kill, producer_chain
)

def ld(kind, base, target, disp):
    opcode = {"ldrb":0x39400000,"ldrh":0x79400000}[kind]
    scale = {"ldrb":1,"ldrh":2}[kind]
    assert disp % scale == 0
    return opcode | ((disp//scale)<<10) | (base<<5) | target

def cmpw(reg, val):
    return 0x7100001f | (val << 10) | (reg << 5)

def binary(*words):
    return b"".join(struct.pack("<I", w) for w in words)

class StaticFieldTests(unittest.TestCase):
    def test_real_arm64_masks(self):
        r = field_load(ld("ldrb",19,5,0x26))
        self.assertEqual((r["field"],r["base_register"],r["target_register"]),(0x26,19,5))
        self.assertEqual(field_load(ld("ldrh",19,4,0x22))["field"],0x22)
        self.assertEqual(cmp_immediate(cmpw(5,99))["compare_register"],5)
        self.assertEqual(movz_immediate(0x52800000 | (68 << 5)),68)
        self.assertIsNone(field_load(0xd503201f))

    def test_same_record_base_with_independent_comparison_attribution(self):
        code = binary(
            ld("ldrh",19,4,0x22),
            ld("ldrb",19,5,0x26),
            ld("ldrb",19,6,0x3a),
            cmpw(5,99),
            0xd65f03c0
        )
        fields, compares, moves = scan(code, 0x1000)
        c,counts,total = evaluate(fields,compares,moves,code,0x1000)
        self.assertEqual(total,1)
        self.assertEqual(counts["SAME_BASE_22_26_3A"],1)
        self.assertEqual(c[0]["nearby_99_100_255_compares"][0]["relation_to_0x26"],
                         "STRAIGHT_LINE_SAME_FIELD_REGISTER_NO_ITEM_BASE_PROOF")
        self.assertFalse(any(x["field"]=="0x99" for x in c[0]["same_base_siblings"]))

    def test_branch_excludes_shared_base(self):
        code = binary(ld("ldrh",19,4,0x22),
                      0xd65f03c0,
                      ld("ldrb",19,5,0x26),
                      0xd65f03c0)
        fields,compare,moves=scan(code,0)
        _,_,total=evaluate(fields,compare,moves,code,0)
        self.assertEqual(total,0)

    def test_base_redefined_between_field_loads_excludes_match(self):
        # mov x19,x20 (ORR alias), then byte field reads through different x19.
        code=binary(ld("ldrh",19,4,0x22),0xaa1403f3,
                    ld("ldrb",19,5,0x26),0xd65f03c0)
        fields,compare,moves=scan(code,0)
        _,_,total=evaluate(fields,compare,moves,code,0)
        self.assertEqual(total,0)

    def test_same_register_has_no_semantic_proof(self):
        code=binary(ld("ldrh",19,4,0x22),ld("ldrb",19,5,0x26),
                    cmpw(7,100),0xd65f03c0)
        fields,compare,moves=scan(code,0)
        c,_,total=evaluate(fields,compare,moves,code,0)
        self.assertEqual(total,1)
        self.assertEqual(c[0]["nearby_99_100_255_compares"][0]["relation_to_0x26"],
                         "DIFFERENT_REGISTER_NOT_DIRECT_FIELD_COMPARE")
        self.assertEqual(c[0]["base_producer"]["status"],
                         "NO_STRAIGHT_LINE_DEFINITION_IN_WINDOW")

if __name__ == "__main__":
    unittest.main()
