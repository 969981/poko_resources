"""Synthetic fixtures for conservative unlinked M7 native-text family triage."""
import csv
import hashlib
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Scripts" / "resources"))
from triage_unlinked_text_families import run

LANGS = ("jp", "en", "fr", "it", "de", "es", "zht", "ko", "zhs")
LANGUAGE_TEXT = ("かな", "english", "français", "italiano", "deutsch",
                 "español", "漢字", "한글", "中文")


def source(vals, flags=0):
    count = len(vals)
    width = 8
    b = bytearray(64 + count * width)
    struct.pack_into("<II", b, 0, count, 0)
    for i, value in enumerate(vals):
        ptr = 64 + i * width
        struct.pack_into("<II", b, ptr, len(b) - ptr, flags)
        b.extend(value.encode("utf-8") + b"\0")
    return bytes(b)


def write_csv(path, fields, records):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(records)


def fixture(root):
    decoded = root / "decoded"
    decoded.mkdir()
    inventory = root / "inventory.csv"
    groups = root / "groups.csv"
    roles = root / "m8.csv"
    table = {}
    # Unique nine-file run: source bitmap matches despite raw metadata changes.
    for i, text in enumerate(LANGUAGE_TEXT):
        table[100 + i] = source([text, "second"], flags=i % 3)
    # An M8 pinned nine-file group, a positive control.
    for i, text in enumerate(LANGUAGE_TEXT):
        table[200 + i] = source([text, "second"], flags=i % 4)
    # 18 consecutive shape-identical files: chunk boundaries are NOT verified.
    for i in range(18):
        table[300 + i] = source([LANGUAGE_TEXT[i % 9], "second"])
    # Unmatched singleton
    table[500] = source(["alone", "single"])
    # One already M7-grouped anchor, excluded from unlinked analysis.
    for i, text in enumerate(LANGUAGE_TEXT):
        table[400 + i] = source([text, "second"])
    inventory_rows = []
    for entry, data in sorted(table.items()):
        (decoded / f"{entry:05d}.bin").write_bytes(data)
        from recover_native_text_ids import parse
        native, status = parse(data, entry, f"decoded/{entry:05d}.bin")
        assert status == "PARSED"
        inventory_rows.append({
            "entry": entry,
            "bytes": len(data),
            "status": "PARSED",
            "sha256": hashlib.sha256(data).hexdigest(),
            "record_count": native.count, "record_width": native.width,
            "nonempty_rows": native.nonempty,
            "bitmap_sha256": native.bitmap,
            "metadata_sha256": native.flaghash,
        })
    write_csv(inventory, list(inventory_rows[0]), inventory_rows)
    write_csv(groups, ["start_entry", "end_entry", "record_count", "forms",
                       "evidence_grade", "category", "locale_order"],
              [{"start_entry": 400, "end_entry": 408, "record_count": 2,
                "forms": 1, "evidence_grade": "STRUCTURE_AND_SCRIPT_WITNESS",
                "category": "UNKNOWN", "locale_order": ",".join(LANGS)}])
    columns = ["target_group_start", "target_text_id", "target_form_index",
               "category", "relationship", "evidence_grade", "parser_source_url"]
    columns += [l + "_entry" for l in LANGS]
    rr = []
    for i in range(2):
        row = {"target_group_start": 200, "target_text_id": i,
               "target_form_index": 0, "category": "Reactions",
               "relationship": "explicit_native_role_table",
               "evidence_grade": "PINNED_PARSER_ROLE_PLUS_NATIVE_ROW",
               "parser_source_url": "fixture-pinned"}
        row.update({l + "_entry": 200 + offset for offset, l in enumerate(LANGS)})
        rr.append(row)
    write_csv(roles, columns, rr)
    return decoded, groups, inventory, roles


class UnlinkedFamilyTriage(unittest.TestCase):
    def test_separates_heuristics_ambiguity_and_m8_proof(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inputs = fixture(root)
            report = run(*inputs, root / "output")
            self.assertEqual(report["native_unlinked_tables_scanned"], 37)
            self.assertEqual(report["original_source_sha256_verified"], 37)
            self.assertEqual(report["m7_linked_tables_excluded"], 9)
            self.assertEqual(report["m8_pinned_role_positive_controls"], {"200": "Reactions"} if False else {200: "Reactions"})
            self.assertEqual(report["exactly_nine_runs"], 2)
            self.assertEqual(report["runs_longer_than_nine_divisible_by_nine"], 1)
            self.assertEqual(report["source_files_in_nine_chunk_runs"], 36)
            self.assertEqual(report["source_files_outside_nine_chunk_runs"], 1)
            self.assertEqual(report["hypothetical_nine_chunks"], 4)
            self.assertEqual(report["new_verified_script_callers"], 0)
            with (root / "output/nine_language_hypotheses_NOT_VERIFIED.csv").open(newline="") as f:
                candidate = {int(x["hypothetical_start_entry"]): x
                             for x in csv.DictReader(f)}
            self.assertEqual(candidate[100]["hypothesis_grade"],
                             "STRUCTURE_AND_SCRIPT_HYPOTHESIS_NOT_VERIFIED")
            self.assertEqual(candidate[100]["metadata_hash_variants_within_chunk"], "3")
            self.assertEqual(candidate[100]["actual_locale_assignment"], "UNVERIFIED")
            self.assertEqual(candidate[200]["hypothesis_grade"], "M8_PINNED_NATIVE_ROLE_TABLE")
            self.assertEqual(candidate[200]["semantic_category"], "Reactions")
            self.assertEqual(candidate[300]["hypothesis_grade"],
                             "AMBIGUOUS_MULTI_GROUP_RUN_NOT_VERIFIED")
            self.assertEqual(candidate[309]["original_boundary_uniquely_supported"], "false")
            self.assertEqual(candidate[100]["positive_script_order_witness"], "true")
            with (root / "output/unsegmented_native_text_tables.csv").open(newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([int(x["source_entry"]) for x in rows], [500])

    def test_hash_corruption_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            decoded, groups, inventory, roles = fixture(root)
            src = decoded / "00100.bin"
            src.write_bytes(src.read_bytes() + b"\0")
            with self.assertRaisesRegex(ValueError, "hash/size mismatch"):
                run(decoded, groups, inventory, roles, root / "out")

    def test_m8_unverified_locale_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            decoded, groups, inventory, roles = fixture(root)
            content = roles.read_text()
            roles.write_text(content.replace(",201,", ",999,", 1))
            with self.assertRaisesRegex(ValueError, "M8 role language/source mismatch"):
                run(decoded, groups, inventory, roles, root / "out")


if __name__ == "__main__":
    unittest.main()
