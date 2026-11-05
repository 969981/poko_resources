"""A full synthetic 17-way export ledger proves no loss, overlap or false success."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from Scripts.resources.export_native_misc_batches import key
from Scripts.resources.reconcile_native_misc_batches import reconcile


class BatchReconcileTests(unittest.TestCase):
    def source(self):
        return [
            {"texture_name":f"icon_test_{i:04d}",
             "category_candidate":"ui_icon_name_candidate",
             "status":"INDEXED_ORIGINAL_TEXINFO_G1T_PAIR",
             "texinfo_hash":f"{i:08x}","g1t_hash":f"{i+1:08x}",
             "texinfo_path":f"t/{i:05d}.texinfo","record_index":"0",
             "g1t_path":f"g/{i:05d}.g1t","layer":"0"}
            for i in range(3930)
        ]

    def make(self,root,source):
        for batch in range(17):
            group=source[batch*240:(batch+1)*240]
            out=root/f"batch_{batch:02d}"
            out.mkdir()
            rows=[]
            for i,r in enumerate(group):
                rows.append({**r,"batch_id":batch,"png_path":f"{out}/id_{i:03d}.png",
                             "png_sha256":"a"*64,"status":"PNG_CANDIDATE_UNVERIFIED","reason":""})
            with (out/"misc_native_sample_manifest.csv").open("w",newline="",encoding="utf-8") as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]))
                w.writeheader();w.writerows(rows)
            audit={"batch_id":batch,"source_scope_rows":3930,
                "indexed_rows_in_batch":len(group),"png_success":len(group),
                "png_unavailable":0,"index_sha256":"b"*64,
                "source_key_sha256":hashlib.sha256("\n".join(
                    "\t".join(key(r)) for r in group).encode()).hexdigest()}
            (out/"batch_audit.json").write_text(json.dumps(audit),encoding="utf-8")

    def test_complete_and_missing_one_partition(self):
        source=self.source()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            self.make(root,source)
            report,rows=reconcile(source,root)
            self.assertEqual(report["status"],"COMPLETE_SOURCE_COVERAGE")
            self.assertEqual(report["png_candidates"],3930)
            self.assertEqual(report["missing_source_records"],0)
            self.assertEqual(len(rows),3930)
            (root/"batch_16"/"batch_audit.json").unlink()
            report,rows=reconcile(source,root)
            self.assertEqual(report["status"],"INCOMPLETE_BATCHES")
            self.assertEqual(report["missing_source_records"],90)
            self.assertEqual(report["absent_batch_ids"],[16])
            self.assertEqual(len(rows),3840)


if __name__=="__main__":
    unittest.main()
