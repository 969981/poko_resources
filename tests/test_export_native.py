"""Native format exports are lossless, bounded and do not modify source blobs."""
import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from Scripts.unpack.export_native import checked_source_path, export_record, run


class NativeExportTests(unittest.TestCase):
    def row(self, data: bytes):
        return {
            "record_id": "root:10349", "source_path": "2.0.1/romfs/KT/0x12345678.fdata",
            "name_hash": "2af82b77", "native_extension_hint": ".kidsobjdb",
            "evidence_grade": "MAGIC_AND_TKID",
            "output_sha256": hashlib.sha256(data).hexdigest(),
            "output_path": "romfs/KT/0x12345678.fdata/decoded/demo.part0001;romfs/KT/0x12345678.fdata/decoded/demo.part0002"
        }

    def test_stream_rejoin_and_sha256_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder) / "UnPack", Path(folder) / "native"
            root = source / "romfs/KT/0x12345678.fdata/decoded"
            root.mkdir(parents=True)
            payload = b"_DOK0000" + b"\x12" * 128
            (root / "demo.part0001").write_bytes(payload[:64])
            (root / "demo.part0002").write_bytes(payload[64:])
            record = self.row(payload)
            r1 = export_record(source, out, record)
            r2 = export_record(source, out, record)
            self.assertEqual(r1["status"], "EXPORTED_HASH_VERIFIED")
            self.assertEqual(r2["status"], "ALREADY_VERIFIED")
            self.assertEqual(Path(r1["destination"]).read_bytes(), payload)
            self.assertEqual((root / "demo.part0001").read_bytes(), payload[:64])

    def test_corrupt_piece_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source, out = Path(folder) / "UnPack", Path(folder) / "native"
            directory = source / "romfs/KT/0x12345678.fdata/decoded"
            directory.mkdir(parents=True)
            (directory / "demo.part0001").write_bytes(b"bad")
            (directory / "demo.part0002").write_bytes(b"data")
            with self.assertRaisesRegex(ValueError, "SHA256_MISMATCH"):
                export_record(source, out, self.row(b"expected"))
            self.assertEqual(list(out.rglob("*.kidsobjdb")), [])

    def test_reject_source_path_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                checked_source_path(Path(folder), "romfs/../../secrets.txt")

    def test_unconfirmed_type_needs_opt_in(self):
        with tempfile.TemporaryDirectory() as folder:
            root, index, out = Path(folder), Path(folder)/"index.csv", Path(folder)/"out"
            with index.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=list(self.row(b"data")) .__iter__())
                w.writeheader()
                row = self.row(b"data")
                row["evidence_grade"] = "EXTERNAL_TKID_INFERRED"
                w.writerow(row)
            self.assertEqual(run(index, root, out, dry_run=True), [])


if __name__ == "__main__":
    unittest.main()
