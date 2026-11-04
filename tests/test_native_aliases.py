"""Native-suffix alias generation reuses Git blob identity without reading assets."""
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Scripts.unpack import native_aliases


class NativeAliasTests(unittest.TestCase):
    def make_index(self, directory, split=True):
        p = Path(directory) / "index.csv"
        parts = ("romfs/KT/0x12345678.fdata/decoded/a.part0001;"
                 "romfs/KT/0x12345678.fdata/decoded/a.part0002") if split else (
                 "romfs/KT/0x12345678.fdata/decoded/a.bin")
        fields = ["record_id", "source_path", "output_path", "name_hash",
                  "native_extension_hint", "evidence_grade", "output_sha256"]
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerow({"record_id": "root:10", "source_path": "2.0.1/romfs/KT/0x12345678.fdata",
                        "output_path": parts, "name_hash": "abcdef12",
                        "native_extension_hint": ".g1m",
                        "evidence_grade": "MAGIC_AND_TKID",
                        "output_sha256": "a" * 64})
            w.writerow({"record_id": "link:1", "source_path": "2.0.1/romfs/LD_C0_R.BIN",
                        "output_path": "romfs/LD_C0_R.BIN/decoded/00001.bin",
                        "name_hash": "", "native_extension_hint": "",
                        "evidence_grade": "UNKNOWN_NATIVE_FORMAT", "output_sha256": "b" * 64})
        return p

    def test_aliases_share_exact_original_blob_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.make_index(tmp)
            a = native_aliases.ROOT.as_posix()
            tree = {
                f"{a}/romfs/KT/0x12345678.fdata/decoded/a.part0001": "a" * 40,
                f"{a}/romfs/KT/0x12345678.fdata/decoded/a.part0002": "b" * 40
            }
            with patch.object(native_aliases, "EXPECTED_TYPED_RECORDS", 1), \
                 patch.object(native_aliases, "EXPECTED_SOURCE_RECORDS", 2):
                records, aliases, counts = native_aliases.native_entries(p, tree)
            self.assertEqual(counts["untyped_link_records"], 1)
            self.assertEqual(counts["native_part_paths"], 2)
            self.assertEqual(len(aliases), 2)
            self.assertTrue(aliases[0][0].endswith("/native/root_000010_abcdef12.g1m.part0001"))
            self.assertEqual(aliases[0][1], "a" * 40)
            self.assertEqual(aliases[1][1], "b" * 40)
            self.assertEqual(records[0]["original_decoded_sha256"], "a" * 64)

    def test_existing_alias_sha_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.make_index(tmp, split=False)
            base = native_aliases.ROOT.as_posix()
            files = {
                f"{base}/romfs/KT/0x12345678.fdata/decoded/a.bin": "a" * 40,
                f"{base}/romfs/KT/0x12345678.fdata/native/root_000010_abcdef12.g1m": "c" * 40,
            }
            with patch.object(native_aliases, "EXPECTED_TYPED_RECORDS", 1), \
                 patch.object(native_aliases, "EXPECTED_SOURCE_RECORDS", 2):
                with self.assertRaisesRegex(ValueError, "EXISTING_NATIVE_BLOB_MISMATCH"):
                    native_aliases.native_entries(p, files)

    def test_duplicate_missing_original_asset_is_never_replaced_with_empty_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.make_index(tmp, split=False)
            with patch.object(native_aliases, "EXPECTED_TYPED_RECORDS", 1), \
                 patch.object(native_aliases, "EXPECTED_SOURCE_RECORDS", 2):
                with self.assertRaisesRegex(ValueError, "SOURCE_BLOB_NOT_IN_GIT_TREE"):
                    native_aliases.native_entries(p, {})


if __name__ == "__main__":
    unittest.main()
