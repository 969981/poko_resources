"""M9.22: a native slot+0x38 call on x22 cannot be promoted to inner x23."""
import unittest

from Scripts.resources.m9_constructor_slot38_receiver import PC,REQUIRED,verify_words


def synthetic_rows():
    out=[]
    for name,(mnemonic,operands) in REQUIRED.items():
        writes=[]
        if operands=="x22, x0":
            writes=["x22"]
        elif operands=="x23, x0":
            writes=["x23"]
        out.append({"pc":PC[name],"mnemonic":mnemonic,"operands":operands,"writes":writes})
    return sorted(out,key=lambda x:x["pc"])


class ConstructorReceiverTests(unittest.TestCase):
    def test_disjoint_original_register_sources(self):
        rows=synthetic_rows()
        writes=verify_words(rows)
        self.assertEqual([x["pc"] for x in writes["x22"]],[PC["source_x22_alias"]])
        self.assertEqual([x["pc"] for x in writes["x23"]],[PC["created_x23_alias"]])
        self.assertNotEqual(PC["source_x22_alias"],PC["created_x23_alias"])

    def test_invalid_implicit_x22_reassignment_fails_closed(self):
        rows=synthetic_rows()
        rows.append({"pc":0xd59230,"mnemonic":"mov","operands":"x22, x9","writes":["x22"]})
        with self.assertRaises(ValueError):
            verify_words(rows)

    def test_synthetic_mismatched_virtual_source_rejected(self):
        rows=synthetic_rows()
        next(x for x in rows if x["pc"]==PC["source_obj_vptr"])["operands"]="x8, [x23]"
        with self.assertRaises(ValueError):
            verify_words(rows)


if __name__=="__main__":unittest.main()
