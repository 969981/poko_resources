"""Synthetic regression tests for historical manifest reconciliation."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Scripts.unpack.reconcile_manifest import run


class ManifestMergeTests(unittest.TestCase):
    def test_previous_published_record_survives_later_batch_skip(self):
        rel = "UnPack/2.0.1/romfs/LD_C0_R.BIN"
        dest = rel + "/decoded/00001.bin"
        manifest = rel + "/_manifest.csv"
        csv_head = "record_id,source_sha256,publish_status,output_path,output_bytes\n"
        published = csv_head + f"1,abc,PUBLISHED,romfs/LD_C0_R.BIN/decoded/00001.bin,3\n"
        skipped = csv_head + f"1,abc,SKIPPED_BATCH_BUDGET,,\n"

        def fake_git(*args):
            if args[0] == "ls-tree":
                return (f"100644 blob {'a'*40} 3\\t{dest}\n"
                        f"100644 blob {'b'*40} 10\\t{manifest}\n").replace("\\t", "\t")
            if args[0] == "log":
                return "old\nnew\n"
            if args[0] == "show":
                return published if args[1].startswith("old:") else skipped
            raise AssertionError(args)

        with tempfile.TemporaryDirectory() as tmp:
            before = Path.cwd()
            os.chdir(tmp)
            try:
                with patch("Scripts.unpack.reconcile_manifest.git", side_effect=fake_git):
                    report = run()
                self.assertEqual(report["overall"]["published_verified"], 1)
                self.assertEqual(report["overall"]["missing_on_git"], 0)
                self.assertEqual(report["overall"]["unmanifested_files"], 0)
                self.assertIn("PUBLISHED", Path(manifest).read_text(encoding="utf-8"))
                self.assertNotIn("SKIPPED_BATCH_BUDGET", Path(manifest).read_text(encoding="utf-8"))
            finally:
                os.chdir(before)


if __name__ == "__main__":
    unittest.main()
