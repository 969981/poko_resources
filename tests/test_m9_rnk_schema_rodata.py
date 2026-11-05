"""M9.5 code-level hash-store and rodata pointer tests."""
from types import SimpleNamespace
import unittest
from Scripts.resources.m9_rnk_schema_rodata import (
    parse_stp_registers,referenced_data
)
class SchemaCodeTests(unittest.TestCase):
    def test_stp_register_pair_sources(self):
        a=SimpleNamespace(mnemonic="stp",op_str="w16, w15, [x11, #-8]")
        b=SimpleNamespace(mnemonic="stp",op_str="x10, x12, [x11], #0x18")
        self.assertEqual(parse_stp_registers(a),("w16","w15",11))
        self.assertEqual(parse_stp_registers(b),("x10","x12",11))
        self.assertIsNone(parse_stp_registers(SimpleNamespace(mnemonic="mov",op_str="w15, #123")))
    def test_rodata_cstring_candidate_not_auto_property_label(self):
        secs=[{"name":"rodata","mem_offset":0x2000,
               "data":b"ABCD"+b"NativeName\x00"+b"\xff\x00"}]
        r=referenced_data(secs,0x2004)
        self.assertEqual(r["candidate_string"],"NativeName")
        self.assertEqual(r["interpretation"],"C_STRING_CANDIDATE_NOT_FIELD_NAME")
    def test_binary_pointer_is_not_a_name(self):
        secs=[{"name":"data","mem_offset":0x1000,
               "data":b"\xff\xfe\xfd\x00"}]
        r=referenced_data(secs,0x1000)
        self.assertEqual(r["candidate_string"],"")
    def test_outside_segments_keeps_unresolved(self):
        self.assertEqual(referenced_data([],0x40)["interpretation"],"UNRESOLVED_ADDRESS")

if __name__=="__main__":unittest.main()
