"""M10 evidence graph: byte provenance, local OID checks, and no false FK claims."""
import csv
import json
import struct
import tempfile
import unittest
from pathlib import Path

from Scripts.resources.build_binary_evidence_graph import build, parse_items


class NativeEvidenceGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.base = root
        self.fields = root / "fields"
        self.fields.mkdir()
        self.output = root / "output"

        raw = bytearray(64 + 3 * 68)
        struct.pack_into("<II", raw, 0, 3, 3)
        for idx in range(3):
            at = 64 + idx * 68
            struct.pack_into("<H", raw, at + 0x22, idx + 20)
            raw[at + 0x26] = 0x10 if idx == 2 else 0x0f
            raw[at + 0x3a] = 4
        self.table = root / "00983.bin"
        self.table.write_bytes(raw)
        self.catalog = root / "catalog.csv"
        with self.catalog.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["item_id","native_name_index","en"])
            w.writeheader()
            w.writerows([
                {"item_id":0,"native_name_index":20,"en":"(Empty)"},
                {"item_id":1,"native_name_index":21,"en":"stone"},
                {"item_id":2,"native_name_index":22,"en":"copper"}
            ])
        self.source = "root:123"
        report = {
            "status":"M9_NATIVE_TYPED_IDOK_PROPERTIES_EXACT",
            "source_kidsobjdb_files_verified":1,
            "native_typed_fields_exported":2,
            "local_oid_equality_candidates_exported":1,
            "files":[{
                "m3_record_id":self.source,
                "source_sha256":"1"*64,
                "verified_native_records":2,
                "verified_typed_property_fields":2,
            }]
        }
        (self.fields / "m9_typed_field_report.json").write_text(json.dumps(report), encoding="utf-8")
        self.typed = self.fields / "native_typed_fields_000.csv"
        data = [
            {"m3_record_id":self.source,"native_node_index":0,
             "object_id_hex":"0x0000000a","object_type_hash_hex":"0xaabbccdd",
             "property_index":0,"property_name_hash_hex":"0x12345678",
             "property_type_code":5,"property_value_count":1,
             "value_byte_offset":100,"value_byte_length":4,
             "value_sha256":"a"*64,"first_u32_values_json":"[2]"},
            {"m3_record_id":self.source,"native_node_index":1,
             "object_id_hex":"0x00000002","object_type_hash_hex":"0xaabbccdd",
             "property_index":0,"property_name_hash_hex":"0x87654321",
             "property_type_code":8,"property_value_count":1,
             "value_byte_offset":200,"value_byte_length":4,
             "value_sha256":"b"*64,"first_u32_values_json":"[]"},
        ]
        with self.typed.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0]))
            w.writeheader()
            w.writerows(data)
        self.edge = self.fields / "unverified_local_oid_candidates_000.csv"
        e = {
            "m3_record_id":self.source,"native_node_index":0,
            "property_index":0,"property_name_hash_hex":"0x12345678",
            "property_type_code":5,"value_absolute_offset":100,
            "source_object_id_hex":"0x0000000a","value_u32_hex":"0x00000002",
            "target_native_node_index":1,
            "evidence_grade":"TYPED_U32_EQUALS_LOCAL_OID_UNVERIFIED_REFERENCE",
            "is_verified_fk":0,
        }
        with self.edge.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(e))
            w.writeheader()
            w.writerow(e)

    def run_build(self):
        return build(self.table, self.catalog, self.fields, self.output,
                     expected_count=3, expected_sha=None)

    def test_candidate_not_upgraded_to_foreign_key(self):
        report = self.run_build()
        self.assertEqual(report["native_nodes"], 2)
        self.assertEqual(report["native_fields"], 2)
        self.assertEqual(report["native_item_records"], 3)
        self.assertEqual(report["item_ids_with_candidate_matches"], 1)
        self.assertEqual(report["local_oid_numeric_equality_candidates"], 1)
        self.assertEqual(report["item_id_to_kids_field_semantic_foreign_keys_verified"], 0)
        self.assertFalse(report["max_stack_field_verified"])
        self.assertTrue((self.output / "native_evidence_graph.sqlite").exists())

    def test_original_name_index_mismatch_rejected(self):
        catalog = list(csv.DictReader(self.catalog.open()))
        catalog[2]["native_name_index"] = "99"
        with self.assertRaisesRegex(ValueError, "NATIVE_NAME_INDEX_MISMATCH"):
            parse_items(self.table.read_bytes(), catalog, expected_count=3, expected_sha=None)

    def test_wrong_local_oid_target_rejected(self):
        contents = self.edge.read_text(encoding="utf-8")
        self.edge.write_text(contents.replace(",1,TYPED_U32_EQUALS_LOCAL_OID_UNVERIFIED_REFERENCE",
                                              ",55,TYPED_U32_EQUALS_LOCAL_OID_UNVERIFIED_REFERENCE"),
                             encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "M9_LOCAL_OID_TARGET_MISMATCH"):
            self.run_build()


if __name__ == "__main__":
    unittest.main()
