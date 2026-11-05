"""M9.23: synthesized unit tests never report a real emulator capture."""
import ast
import json
import unittest
from pathlib import Path

from Scripts.resources.m9_runtime_callback_trace_validator import (
    validate,SHA,
)


BASE=0x7100000000


def header():
    return {"kind":"m9_23_capture_session",
            "main_base":hex(BASE),
            "expected_unrelocated_original_main_sha256":SHA}


def hit(kind,offset,**kwargs):
    return {"kind":"m9_23_native_runtime_breakpoint_hit",
            "target":kind,"main_offset":hex(offset),
            "breakpoint_pc":hex(BASE+offset),
            "registers":{"x0":hex(0x7200000000),
                         "x3":hex(0x7200001234),
                         "x19":hex(0x7200001234),
                         "x23":hex(0x7200004567)},
            "object_x0_vptr":kwargs.get("vptr"),
            "object_x0_vptr_plus_0x38_callback":kwargs.get("method"),
            "owner_x3_plus_0x28":None,
            "owner_x19_plus_0x28":None}


class RuntimeCaptureTests(unittest.TestCase):
    def test_original_gdb_python_script_syntax_without_importing_gdb(self):
        p=Path("Scripts/resources/m9_gdb_owner_callback_trace.py")
        ast.parse(p.read_text(encoding="utf-8"),filename=str(p))

    def test_capture_with_positive_matching_callback_entry(self):
        records=[header(),hit("actual_inner_descriptor_callback_entry",
                              0xd59420,
                              vptr=hex(BASE+0x32fdfa0),
                              method=hex(BASE+0xd59420))]
        result=validate([json.dumps(x) for x in records])
        self.assertEqual(result["inner_descriptor_entry_hits_with_expected_vptr_and_slot_bytes"],1)
        self.assertFalse(result["specific_vptr_slot0x38_indirect_call_path_proven"])
        self.assertEqual(result["M7_script_text_foreign_keys_proven"],0)

    def test_other_receiver_is_not_inner_class_hit(self):
        records=[header(),hit("source_x22_slot38_blr",0xd59250,
                              vptr=hex(BASE+0x32fdfa0),
                              method=hex(BASE+0xd59420))]
        result=validate([json.dumps(x) for x in records])
        self.assertEqual(result["inner_descriptor_entry_hits_with_expected_vptr_and_slot_bytes"],0)

    def test_inconsistent_pc_rejected(self):
        r=hit("actual_inner_descriptor_callback_entry",0xd59420)
        r["breakpoint_pc"]=hex(BASE+0xd59424)
        with self.assertRaises(ValueError):
            validate([json.dumps(header()),json.dumps(r)])

    def test_empty_capture_is_not_claimed_to_be_runtime_success(self):
        result=validate([json.dumps(header())])
        self.assertEqual(result["status"],"M9_CAPTURE_HAS_NO_BREAKPOINT_HITS")

    def test_matching_owner_from_x3_remains_lifetime_unverified(self):
        a=hit("owner_constructor_before_store",0xd59274)
        b=hit("owner_cleanup_entry",0xd58e34)
        r=validate([json.dumps(x) for x in [header(),a,b]])
        self.assertEqual(len(r["matching_user_observed_constructor_owner_and_later_x3_event_pairs"]),1)
        self.assertEqual(r["inner_descriptor_entry_hits_with_expected_vptr_and_slot_bytes"],0)


if __name__=="__main__":unittest.main()
