"""Coverage regression tests with synthetic IDX/RDB/RDX and reconciled manifests."""
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch

from Scripts.unpack.coverage import ROOT, scan


class CoverageTests(unittest.TestCase):
    def setup_data(self, missing=True):
        source = "0x00000001.fdata"
        def record(i, magic, offset=0):
            return N(record_index=i, footer_magic=magic, footer_layout="standard_13",
                     fdata_index=(1 if i == 1 else 0), name_hash=(0x25768c1b if magic == 0x0c01 else 111 + i),
                     type_hash=201 + i, uncompressed_size=100)
        root = [record(0, 0x0401), record(1, 0x0401), record(2, 0x0c01)]
        rdx = [N(filename=source, platform_flags=0xffff), N(filename="0x00000002.fdata", platform_flags=0xffff)]
        link = [N(index=0, stored_size=13), N(index=1, stored_size=0), N(index=2, stored_size=128)]
        kt_manifest = "UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00000001.fdata/_manifest.csv"
        link_manifest = "UnPack/2.0.1/romfs/LD_C0_R.BIN/_manifest.csv"
        names = [kt_manifest, link_manifest, f"{ROOT}/{source}"]
        if not missing:
            names.append(f"{ROOT}/data/0x25768c1b.file")
        values = {
            kt_manifest: "record_id,publish_status\nroot:0,PUBLISHED\n",
            link_manifest: "record_id,publish_status\n0,PUBLISHED\n2,PUBLISHED\n",
            "UnPack/2.0.1/_reports/manifest_reconciliation.json":
                '{"overall":{"published_verified_size":3,"missing_or_wrong_size":0,"unmanifested_output_files":0}}'
        }
        def fake_read(p):
            return values.get(p, b"").encode() if isinstance(values.get(p, b""), str) else values.get(p, b"")
        def fake_rdb(data, catalog, entries):
            return (root if catalog == "root" else []), {}
        return names, fake_read, fake_rdb, rdx, link

    def test_missing_file_and_container_are_tracked_without_false_success(self):
        names, reader, rdb, rdx, link = self.setup_data()
        with patch("Scripts.unpack.coverage.parse_rdb", side_effect=rdb), \
             patch("Scripts.unpack.coverage.parse_rdx", return_value=rdx), \
             patch("Scripts.unpack.coverage.parse_idx", return_value=link):
            result, missing, unpublished = scan(names, read=reader)
        overall = result["overall"]
        self.assertEqual(overall["rdb_published"], 1)
        self.assertEqual(overall["missing_source_records"], 2)
        self.assertEqual(overall["link_published"], 2)
        self.assertEqual(overall["link_empty_index_entries"], 1)
        self.assertEqual(overall.get("source_present_unpublished", 0), 0)
        self.assertEqual(len(missing), 2)
        self.assertEqual(len(result["missing_sources"]), 2)
        self.assertEqual(result["coverage"]["rdb_published_of_total"], [1, 3])
        self.assertFalse(unpublished)

    def test_unpublished_present_file_remains_incomplete(self):
        names, reader, rdb, rdx, link = self.setup_data(missing=False)
        with patch("Scripts.unpack.coverage.parse_rdb", side_effect=rdb), \
             patch("Scripts.unpack.coverage.parse_rdx", return_value=rdx), \
             patch("Scripts.unpack.coverage.parse_idx", return_value=link):
            result, missing, unpublished = scan(names, read=reader)
        self.assertEqual(result["overall"]["source_present_unpublished"], 1)
        self.assertEqual(result["overall"]["missing_source_records"], 1)
        self.assertEqual(unpublished[0]["source_file"], "0x25768c1b.file")

    def test_reject_mismatched_git_tree_audit(self):
        names, reader, rdb, rdx, link = self.setup_data()
        def invalid(p):
            if p.endswith("manifest_reconciliation.json"):
                return b'{"overall":{"published_verified_size":2}}'
            return reader(p)
        with patch("Scripts.unpack.coverage.parse_rdb", side_effect=rdb), \
             patch("Scripts.unpack.coverage.parse_rdx", return_value=rdx), \
             patch("Scripts.unpack.coverage.parse_idx", return_value=link):
            with self.assertRaisesRegex(ValueError, "PUBLISHED_COUNT_MISMATCH"):
                scan(names, read=invalid)


if __name__ == "__main__":
    unittest.main()
