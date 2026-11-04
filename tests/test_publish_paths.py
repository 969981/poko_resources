"""Publication path and byte-level smoke tests without game assets."""
import csv
import tempfile
import unittest
from pathlib import Path

from Scripts.unpack.publish import source_directory, publish_rows


class PublishTest(unittest.TestCase):
    def test_linkdata_path(self):
        self.assertEqual(source_directory(Path("UnPack/2.0.1"), "linkdata",
                                           Path("/tmp/LD_C0_R.BIN")),
                         Path("UnPack/2.0.1/romfs/LD_C0_R.BIN"))

    def test_ktrdb_paths(self):
        with tempfile.TemporaryDirectory() as t:
            base = Path(t) / "KT"
            source = base / "MountPoint_1/0x00176283.fdata"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"data")
            self.assertEqual(source_directory(Path(t) / "out", "ktrdb", source, base),
                             Path(t) / "out/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/MountPoint_1/0x00176283.fdata")

    def test_decoded_published_and_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            source = root / "LD_C0_R.BIN"
            source.write_bytes(b"source")
            scratch = root / "scratch/decoded"
            scratch.mkdir(parents=True)
            (scratch / "00001.bin").write_bytes(b"decoded")
            out = root / "UnPack/2.0.1"
            rows = [{"index": "1", "status": "DECOMPRESSED", "offset": "0",
                     "stored_size": "8", "unpacked_size": "7", "error": ""}]
            report = publish_rows(rows, "linkdata", root / "scratch", out, source,
                                  max_file=100, max_total=100)
            self.assertEqual(report["publish_statuses"].get("PUBLISHED"), 1)
            self.assertEqual((out / "romfs/LD_C0_R.BIN/decoded/00001.bin").read_bytes(), b"decoded")
            self.assertIn("source_sha256",
                          (out / "romfs/LD_C0_R.BIN/_manifest.csv").read_text())

    def test_large_blob_skipped(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            src = root / "LD_C0_R.BIN"
            src.write_bytes(b"source")
            (root / "scratch/decoded").mkdir(parents=True)
            (root / "scratch/decoded/00000.bin").write_bytes(b"large payload")
            result = publish_rows([{"index": "0", "status": "DECOMPRESSED", "offset": "0",
                                    "stored_size": "13", "unpacked_size": "13"}],
                                  "linkdata", root / "scratch", root / "out", src,
                                  max_file=2, max_total=100)
            self.assertEqual(result["publish_statuses"].get("SKIPPED_GITHUB_FILE_LIMIT"), 1)
            self.assertFalse((root / "out/romfs/LD_C0_R.BIN/decoded/00000.bin").exists())


if __name__ == "__main__":
    unittest.main()
