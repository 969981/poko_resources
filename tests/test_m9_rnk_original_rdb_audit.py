"""M9.6: exact RDB hash matching and fail-closed RNK evidence."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from Scripts.resources.m9_rnk_original_rdb_audit import (
    expected_hashes, source_candidates, input_status, inventory, write_results,
)


def record(name_hash, idx=4, footer=0x0401, layout="standard_13"):
    return SimpleNamespace(
        name_hash=name_hash, record_index=idx, rdb_offset=0x100 + idx * 80,
        type_hash=0x1234, flags=0, footer_layout=layout,
        footer_magic=footer, fdata_index=0, fdata_offset=0x200,
        fdata_entry_size=0x80, uncompressed_size=0x60,
    )


class OriginalRdbAuditTests(unittest.TestCase):
    def test_hashes_are_original_header_values(self):
        self.assertEqual(expected_hashes({"source_name_hashes": {
            "root:1": "aa91cb96", "root:2": "0xa91711c6", "root:3": "cb3c8b15",
        }}), {"aa91cb96", "a91711c6", "cb3c8b15"})
        with self.assertRaises(ValueError):
            expected_hashes({"source_name_hashes": {"a": "not-hex"}})

    def test_rdx_provenance_and_archive_vs_absence(self):
        base = Path("2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE")
        rdx = [SimpleNamespace(filename="0xbeef.fdata", platform_flags=0xff01)]
        paths = source_candidates(record(0xaa91cb96), rdx, base)
        self.assertEqual(paths[0], (base / "MountPoint_1/0xbeef.fdata").as_posix())
        self.assertEqual(input_status(paths, {paths[0] + ".7z.001"}),
                         "SPLIT_7Z_TRACKED_UNREAD")
        self.assertEqual(input_status(paths, {paths[0]}), "RAW_CONTAINER_TRACKED_UNREAD")
        self.assertEqual(input_status(paths, set()), "NO_PHYSICAL_CONTAINER_IN_GIT_TREE")
        self.assertEqual(source_candidates(record(0xaa91cb96, layout="opaque_17"), rdx, base), [])

    def test_index_match_is_not_name_table_or_fk(self):
        base = Path("2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE")
        catalogs = {"root": (
            [record(0xaa91cb96), record(0xdeadbeef, 5)],
            [SimpleNamespace(filename="0xbeef.fdata", platform_flags=0xffff)],
            {"rdb_sha256": "x", "rdx_sha256": "y", "advertised_records": 2, "rdx_entries": 1},
        )}
        rows, totals = inventory(catalogs, {"aa91cb96", "cb3c8b15"}, set(), base)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["record_id"], "root:4")
        self.assertFalse(rows[0]["rnk_magic_verified"])
        self.assertFalse(rows[0]["script_text_fk_verified"])
        with tempfile.TemporaryDirectory() as td:
            report = write_results(Path(td), {"aa91cb96", "cb3c8b15"}, rows, totals, 89507)
            self.assertEqual(report["rnk_payloads_verified"], 0)
            self.assertEqual(report["new_script_scene_quest_building_text_foreign_keys"], 0)
            self.assertEqual(report["per_hash"][0]["original_rdb_index_hits"], 1)
            self.assertEqual(report["per_hash"][1]["original_rdb_index_hits"], 0)
            written = json.loads((Path(td)/"rnk_original_rdb_audit.json").read_text())
            self.assertEqual(written, report)


if __name__ == "__main__":
    unittest.main()
