"""M9.16 strict direct BL target and bounded frame/provenance tests."""
import struct
import unittest
from Scripts.resources.m9_owner_local_callgraph import decode_bl_target, classify_local

class OwnerCallerTests(unittest.TestCase):
    def test_direct_bl_positive_and_negative_offsets(self):
        self.assertEqual(decode_bl_target(0x94000010,0x1000),0x1040)
        self.assertEqual(decode_bl_target(0x97ffffff,0x1000),0xffc)
        self.assertIsNone(decode_bl_target(0xd63f0100,0x1000))
        self.assertIsNone(decode_bl_target(0x14000010,0x1000))

    def test_x19_write_and_local_pointer_load_are_untyped(self):
        rows=[
            {"pc":0xD591A0,"mnemonic":"mov","operands":"x19, x0",
             "writes":["x19"],"u32":"aa0003f3"},
            {"pc":0xD59274,"mnemonic":"str","operands":"x23, [x19, #0x28]",
             "writes":[],"u32":"f9001677"},
            {"pc":0xD59280,"mnemonic":"ldr","operands":"x0, [x19, #0x28]",
             "writes":["x0"],"u32":"f9401660"},
        ]
        r=classify_local(rows)
        self.assertEqual(len(r["x19_writes_nearest_prior_to_object_escape"]),1)
        self.assertEqual(len(r["local_owner_field_0x28_loads"]),1)
        self.assertEqual(r["local_owner_field_0x28_loads"][0]["base_register"],"x19")

if __name__=="__main__":
    unittest.main()
