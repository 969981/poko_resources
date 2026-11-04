"""Synthetic, network-free verification of historical manifest recovery."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from Scripts.unpack.reconcile_manifest import run


class ManifestMergeTest(unittest.TestCase):
    def test_prior_published_not_overwritten_by_budget_skip(self):
        folder = "UnPack/2.0.1/romfs/LD_C0_R.BIN"
        dest = folder + "/decoded/00001.bin"
        manifest = folder + "/_manifest.csv"
        header = "record_id,source_sha256,publish_status,output_path,output_bytes\n"
        original = header + "1,abc,PUBLISHED,romfs/LD_C0_R.BIN/decoded/00001.bin,3\n"
        later = header + "1,abc,SKIPPED_BATCH_BUDGET,,\n"

        def fake_git(*args):
            if args[0] == "ls-tree":
                return dest + "\n" + manifest + "\n"
            if args[0] == "log":
                return "old\nnew\n"
            if args[0] == "show":
                return original if args[1].startswith("old:") else later
            raise AssertionError(args)

        def fake_tree_sha(path):
            return "123abc" if path == folder + "/decoded" else None

        def fake_tree_reader(repo, sha, token):
            self.assertEqual(repo, "969981/poko_resources")
            self.assertEqual(sha, "123abc")
            self.assertEqual(token, "test-token")
            return {"00001.bin": 3}

        with tempfile.TemporaryDirectory() as temporary:
            cwd = Path.cwd()
            os.chdir(temporary)
            try:
                with patch("Scripts.unpack.reconcile_manifest.git", side_effect=fake_git):
                    with patch("Scripts.unpack.reconcile_manifest.tree_sha", side_effect=fake_tree_sha):
                        result = run(repo="969981/poko_resources",
                                     github_token="test-token",tree_reader=fake_tree_reader)
                self.assertEqual(result["overall"]["published_verified_size"], 1)
                self.assertEqual(result["overall"]["missing_or_wrong_size"], 0)
                self.assertEqual(result["overall"]["unmanifested_output_files"], 0)
                text = Path(manifest).read_text(encoding="utf-8")
                self.assertIn("PUBLISHED", text)
                self.assertNotIn("SKIPPED_BATCH_BUDGET", text)
            finally:
                os.chdir(cwd)

    def test_size_mismatch_is_classified_not_counted(self):
        folder = "UnPack/2.0.1/romfs/LD_C0_R.BIN"
        dest = folder + "/decoded/00001.bin"
        manifest = folder + "/_manifest.csv"
        row = ("record_id,source_sha256,publish_status,output_path,output_bytes\n"
               "1,abc,PUBLISHED,romfs/LD_C0_R.BIN/decoded/00001.bin,5\n")

        def fake_git(*args):
            if args[0] == "ls-tree":
                return dest + "\n" + manifest + "\n"
            if args[0] == "log":
                return "old\n"
            if args[0] == "show":
                return row
            raise AssertionError(args)

        with tempfile.TemporaryDirectory() as temp:
            cwd = Path.cwd()
            os.chdir(temp)
            try:
                with patch("Scripts.unpack.reconcile_manifest.git", side_effect=fake_git):
                    with patch("Scripts.unpack.reconcile_manifest.tree_sha", return_value="sha"):
                        report = run(repo="969981/poko_resources", github_token="token",
                                     tree_reader=lambda repo, sha, token: {"00001.bin": 3})
                self.assertEqual(report["overall"]["missing_or_wrong_size"], 1)
                self.assertEqual(report["overall"]["published_verified_size"], 0)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
