"""No native extension is treated as validated from an external hash alone."""
import csv
import tempfile
import unittest
from pathlib import Path

from Scripts.unpack.m3_types import judge, run


class M3TypeIndexTests(unittest.TestCase):
    def test_magic_and_type_hash_agreement(self):
        self.assertEqual(judge("20a6a0bb", "KIDSOBJDB_SIGNATURE")[0:2],
                         (".kidsobjdb", "MAGIC_AND_TKID"))
        self.assertEqual(judge("563bdef1", "UNKNOWN_BINARY")[0:2],
                         (".g1m", "EXTERNAL_TKID_INFERRED"))
        self.assertEqual(judge("563bdef1", "G1A_ANIMATION_CONTAINER")[0:2],
                         ("", "HASH_MAGIC_CONFLICT"))
        self.assertEqual(judge("ffffffff", "UNKNOWN_BINARY")[0:2],
                         ("", "UNKNOWN_NATIVE_FORMAT"))

    def test_join_real_published_ids_and_skip_empty_link_slots(self):
        with tempfile.TemporaryDirectory() as root:
            r = Path(root)
            src = r / "m3.csv"
            with src.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=[
                    "record_id", "catalog", "record_index", "type_hash",
                    "signature", "status", "head_64_hex", "name_hash", "unpacked_size"])
                w.writeheader()
                w.writerow({"record_id":"root:3", "catalog":"root", "record_index":3,
                            "type_hash":"20a6a0bb", "signature":"KIDSOBJDB_SIGNATURE",
                            "status":"PROBED", "unpacked_size":"96"})
                w.writerow({"record_id":"link:0", "catalog":"link", "record_index":0,
                            "type_hash":"", "signature":"EMPTY_INDEX", "status":"EMPTY_INDEX"})
                w.writerow({"record_id":"link:1", "catalog":"link", "record_index":1,
                            "type_hash":"", "signature":"UNKNOWN_BINARY", "status":"PROBED",
                            "unpacked_size":"100"})
            manifests = {
                "root:3":{"output_path":"romfs/KT/decoded/root3.bin",
                          "output_sha256":"abc", "source_path":"2.0.1/romfs/KT"},
                "link:1":{"output_path":"romfs/LINK/decoded/00001.bin",
                          "output_sha256":"def", "source_path":"2.0.1/romfs/LINK"}
            }
            result = run(src, r / "out", manifest_index=manifests)
            self.assertEqual(result["published_records"], 2)
            self.assertEqual(result["status_counts"]["MAGIC_AND_TKID"], 1)
            self.assertEqual(result["status_counts"]["UNKNOWN_NATIVE_FORMAT"], 1)


if __name__ == "__main__":
    unittest.main()
