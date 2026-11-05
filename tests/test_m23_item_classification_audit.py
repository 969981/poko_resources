"""Synthetic regression: source identity audit never upgrades an enum or loader."""
import hashlib
import unittest
from Scripts.resources.m23_item_classification_audit import (
    audit, SCHEMA, MAIN_SHA, ITEM_SHA
)


def table():
    b = bytearray(64 + 4600 * 68)
    b[:8] = (4600).to_bytes(4, "little") + (3).to_bytes(4, "little")
    for i, kind in ((6, 15), (101, 16), (102, 16), (302, 4)):
        at = 64 + i * 68
        b[at + 0x22:at + 0x24] = (i + 1).to_bytes(2, "little")
        b[at + 0x26] = kind
    return bytes(b)


def header():
    return {
        "schema": SCHEMA, "event": "session",
        "source_main_file_sha256": MAIN_SHA,
        "source_item_table_sha256": ITEM_SHA,
        "main_executable_mapped_identity_verified": False,
    }


def field(src, item_id, wrong=False):
    original = src[64 + item_id * 68:64 + (item_id + 1) * 68]
    runtime = bytearray(original)
    if wrong:
        runtime[17] ^= 1
    return {
        "schema": SCHEMA, "event": "field_26_loop_a",
        "item_id": item_id, "record_ptr": hex(0x100000 + item_id * 68),
        "runtime_record_hex": runtime.hex(),
        "runtime_record_sha256": hashlib.sha256(runtime).hexdigest(),
        "source_record_sha256": hashlib.sha256(original).hexdigest(),
        "source_raw_kind_u8": original[0x26],
        "runtime_raw_kind_u8": runtime[0x26],
        "status": "FULL_68_BYTE_MATCH" if not wrong else "LAYOUT_DIFF_OR_UNRELATED",
    }


class M23AuditTests(unittest.TestCase):
    def test_requires_three_different_ids_material_candidate_and_other(self):
        source = table()
        result = audit([header(), field(source, 6), field(source, 101),
                        field(source, 302)], source)
        self.assertTrue(result["exact_record_identity_criteria_met"])
        self.assertEqual(result["full_match_ids"], [6, 101, 302])
        self.assertFalse(result["original_00983_loader_proven"])
        self.assertFalse(result["official_item_kind_enum_proven"])

    def test_68byte_mismatch_does_not_count_even_if_kind_equal(self):
        source = table()
        result = audit([header(), field(source, 6), field(source, 101, True),
                        field(source, 302)], source)
        self.assertFalse(result["exact_record_identity_criteria_met"])
        self.assertEqual(result["distinct_full_match_ids"], 2)
        self.assertEqual(result["mismatches"][0]["diff_bytes"], 1)

    def test_requires_multiple_different_pointers(self):
        source = table()
        rows = [field(source, i) for i in (6, 101, 302)]
        for e in rows:
            e["record_ptr"] = "0x1"
        result = audit([header(), *rows], source)
        self.assertFalse(result["exact_record_identity_criteria_met"])

    def test_bad_session_hash_rejected(self):
        source = table()
        h = header()
        h["source_main_file_sha256"] = "stale"
        with self.assertRaisesRegex(ValueError, "IDENTITY"):
            audit([h, field(source, 101)], source)

    def test_two_vtable_method_targets_reported_without_semantic_proof(self):
        source = table()
        events = [header(),
                  {"schema": SCHEMA, "event": "v1_call", "v1_method": "0x1111"},
                  {"schema": SCHEMA, "event": "v2_tailcall", "v2_method": "0x2222"}]
        result = audit(events, source)
        self.assertEqual(result["dynamic_v1_targets"], ["0x1111"])
        self.assertEqual(result["dynamic_v2_targets"], ["0x2222"])
        self.assertFalse(result["original_00983_loader_proven"])


if __name__ == "__main__":
    unittest.main()
