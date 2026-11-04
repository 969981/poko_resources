"""M4 source-sharded KIDSOBJDB parsing and exact-shard aggregation."""
import csv
import gzip
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Scripts.unpack import m4_batch, m4_aggregate


def document():
    block = (b"IDOK0000" + struct.pack("<4I", 68, 0x11223344, 0x55667788, 1)
             + struct.pack("<3I", 5, 8, 0xaabbccdd)
             + struct.pack("<8I", *range(8)))
    blob = b"_DOK0000" + struct.pack("<5I", 28, 1, 1, 0xabcdef, 96) + block
    assert len(blob) == 96
    return blob


class M4BatchTests(unittest.TestCase):
    def test_one_real_shape_record_is_hash_checked_and_parsed(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "UnPack/2.0.1"
            path = root / "romfs/source.fdata/decoded/original.bin"
            path.parent.mkdir(parents=True)
            blob = document()
            path.write_bytes(blob)
            index = base / "m3_index.csv"
            with index.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=[
                    "record_id", "source_path", "name_hash", "type_hash",
                    "native_extension_hint", "evidence_grade", "output_path", "output_sha256"])
                w.writeheader()
                w.writerow({
                    "record_id": "root:1", "source_path": "2.0.1/romfs/source.fdata",
                    "name_hash": "1234", "type_hash": "20a6a0bb",
                    "native_extension_hint": ".kidsobjdb", "evidence_grade": "MAGIC_AND_TKID",
                    "output_path": "romfs/source.fdata/decoded/original.bin",
                    "output_sha256": hashlib.sha256(blob).hexdigest()})
            with patch.object(m4_batch, "ROOT", root):
                patterns = base / "sparse.txt"
                selected = m4_batch.plan(index, 0, 1, patterns)
                self.assertEqual(len(selected), 1)
                self.assertIn("/UnPack/2.0.1/romfs/source.fdata/decoded/original.bin",
                              patterns.read_text())
                file = base / "out/m4_shard00.jsonl.gz"
                summary = m4_batch.inspect(index, 0, 1, file)
                self.assertEqual(summary["statuses"], {"FIXED_WIDTH_ONLY": 1})
                with gzip.open(file, "rt", encoding="utf-8") as f:
                    row = json.loads(f.readline())
                self.assertEqual(row["decoded"]["summary"]["IDOK"], 1)
                self.assertEqual(row["decoded"]["blocks"][0]["properties"][0]["sample_values"], list(range(8)))
                # Corrupt source must never be silently declared valid.
                path.write_bytes(b"invalid")
                result = m4_batch.inspect(index, 0, 1, file)
                self.assertEqual(result["statuses"], {"PARSE_FAILED": 1})

    def test_all_shards_join_without_duplicate_or_missing_records(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            index = base / "types.csv"
            with index.open("w", newline="", encoding="utf-8") as f:
                fields = ["record_id", "native_extension_hint", "evidence_grade"]
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                for id in ("root:1", "root:2"):
                    w.writerow({"record_id": id, "native_extension_hint": ".kidsobjdb",
                                "evidence_grade": "MAGIC_AND_TKID"})
            parts = base / "parts"
            parts.mkdir()
            for shard in range(2):
                ids = [r["record_id"] for r in m4_batch.select_rows(index, shard, 2)]
                stem = f"m4_shard{shard:02d}"
                with (parts / (stem + ".csv")).open("w", newline="", encoding="utf-8") as f:
                    w = csv.DictWriter(f, fieldnames=["record_id", "status", "idok_blocks", "rdok_blocks",
                                                       "unsupported_field_types", "partial_blocks", "warnings"])
                    w.writeheader()
                    for rid in ids:
                        w.writerow({"record_id": rid, "status": "FIXED_WIDTH_ONLY", "idok_blocks": 1,
                                    "rdok_blocks": 0, "unsupported_field_types": 0, "partial_blocks": 0, "warnings": ""})
                with gzip.open(parts / (stem + ".jsonl.gz"), "wt", encoding="utf-8") as f:
                    for rid in ids:
                        f.write(json.dumps({"record_id": rid, "status": "FIXED_WIDTH_ONLY"}) + "\n")
                (parts / (stem + ".summary.json")).write_text(json.dumps({
                    "shard": shard, "shards": 2, "selected_records": len(ids)
                }), encoding="utf-8")
            result = m4_aggregate.run(parts, index, base / "out", shards=2, expected_total=2)
            self.assertEqual(result["reported_records"], 2)
            self.assertEqual(result["unresolved_records"], 0)
            self.assertTrue(result["metadata_complete"])


if __name__ == "__main__":
    unittest.main()
