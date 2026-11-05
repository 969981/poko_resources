"""Tests for conservative M7/M9 table catalog and verified typed-row joins."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Scripts" / "resources"))
from build_native_text_catalog import run


def write_csv(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def fixture(root):
    m7, grouped, unlinked, dest = [root / name for name in ("m7", "grouped", "unlinked", "dest")]
    for folder in (m7, grouped, unlinked):
        folder.mkdir()
    groups = [{
        "start_entry": 50, "end_entry": 58, "record_count": 2, "forms": 1,
        "evidence_grade": "STRUCTURE_ONLY", "category": "UNKNOWN",
        "locale_order": "jp,en,fr,it,de,es,zht,ko,zhs",
    }]
    write_csv(m7 / "nine_language_groups.csv", list(groups[0]), groups)
    inventory = [{
        "entry": e, "status": "PARSED", "sha256": "a" * 64,
        "record_count": 2, "record_width": 8
    } for e in [20, *range(50, 59)]]
    write_csv(m7 / "native_table_inventory.csv", list(inventory[0]), inventory)
    (grouped / "text_export_report.json").write_text(json.dumps({
        "groups_exported": 1, "table_groups": [{"start_entry": 50}],
        "full_game_coverage": "NOT_CLAIMED",
    }))
    (unlinked / "unlinked_text_export_report.json").write_text(json.dumps({
        "tables_exported": 1, "table_entries": [{"entry": 20}],
        "full_game_coverage": "NOT_CLAIMED",
    }))
    edge_path = root / "edges.csv"
    edge = {
        "edge_id": "item:1", "source_domain": "Item", "source_record_id": 1,
        "source_entry": 983, "source_field_offset": 102,
        "field_type": "u16 item.name_index",
        "target_group_start": 50, "target_text_id": 1, "target_form_index": 0,
        "category": "Items", "evidence_grade": "NATIVE_TYPED_FIELD_PARSER",
        "parser_evidence": "unit-test", "intermediates": "",
    }
    write_csv(edge_path, list(edge), [edge])
    return m7, grouped, unlinked, edge_path, dest


class NativeTextCatalog(unittest.TestCase):
    def test_catalog_preserves_unlinked_unknown_and_verified_row_scope(self):
        with tempfile.TemporaryDirectory() as d:
            params = fixture(Path(d))
            report = run(*params)
            self.assertEqual(report["native_text_tables"], 10)
            self.assertEqual(report["nine_language_source_tables"], 9)
            self.assertEqual(report["unlinked_native_text_tables"], 1)
            self.assertEqual(report["typed_resource_edges_from_m9"], 1)
            self.assertEqual(report["verified_new_script_to_text_caller_edges"], 0)
            with (params[-1] / "native_text_table_catalog.csv").open(newline="") as f:
                catalog = list(csv.DictReader(f))
            self.assertEqual(catalog[0]["source_entry"], "20")
            self.assertEqual(catalog[0]["locale_candidate"], "UNKNOWN")
            self.assertEqual(catalog[0]["business_category"], "UNKNOWN")
            self.assertEqual(catalog[1]["locale_status"], "M7_STRUCTURAL_CANDIDATE")
            with (params[-1] / "m9_verified_text_row_links.csv").open(newline="") as f:
                edges = list(csv.DictReader(f))
            self.assertEqual(edges[0]["target_text_id"], "1")
            self.assertEqual(edges[0]["script_caller_verified"], "false")

    def test_m8_pinned_role_restores_locale_identity_outside_m7_groups(self):
        with tempfile.TemporaryDirectory() as d:
            m7, grouped, unlinked, edge_path, dest = fixture(Path(d))
            inventory = m7 / "native_table_inventory.csv"
            with inventory.open("a", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                for entry in range(80, 89):
                    w.writerow([entry, "PARSED", "a" * 64, 2, 8])
            (unlinked / "unlinked_text_export_report.json").write_text(json.dumps({
                "tables_exported": 10,
                "table_entries": [{"entry": e} for e in [20, *range(80, 89)]],
                "full_game_coverage": "NOT_CLAIMED"
            }))
            m8_path = Path(d) / "m8_roles.csv"
            lang_columns = [f"{l}_entry" for l in
                            ("jp", "en", "fr", "it", "de", "es", "zht", "ko", "zhs")]
            columns = ["category", "target_group_start", "target_text_id",
                       "target_form_index", "relationship", "evidence_grade",
                       "parser_source_url", *lang_columns]
            role_rows = []
            for text_id in range(2):
                row = dict(category="Reactions", target_group_start=80,
                           target_text_id=text_id, target_form_index=0,
                           relationship="explicit_native_role_table",
                           evidence_grade="PINNED_PARSER_ROLE_PLUS_NATIVE_ROW",
                           parser_source_url="pinned-test-parser")
                row.update({l: 80 + i for i, l in enumerate(lang_columns)})
                role_rows.append(row)
            write_csv(m8_path, columns, role_rows)
            with edge_path.open("a", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow([
                    "reaction:1", "Reactions", "1", "33", "0", "u16 id",
                    "80", "1", "0", "Reactions", "NATIVE_TYPED_FIELD_PARSER",
                    "pinned-test-parser", "",
                ])
            report = run(m7, grouped, unlinked, edge_path, dest, m8_path)
            self.assertEqual(report["m8_source_verified_role_tables"], 9)
            self.assertEqual(report["unlinked_tables_with_m9_verified_typed_edges"], 9)
            with (dest / "native_text_table_catalog.csv").open(newline="") as f:
                catalog = {int(r["source_entry"]): r for r in csv.DictReader(f)}
            self.assertEqual(catalog[80]["locale_candidate"], "jp")
            self.assertEqual(catalog[88]["locale_candidate"], "zhs")
            self.assertEqual(catalog[80]["business_category"], "Reactions")
            self.assertEqual(catalog[20]["business_category"], "UNKNOWN")

    def test_reject_invalid_m9_row_index(self):
        with tempfile.TemporaryDirectory() as d:
            m7, grouped, unlinked, edge_path, dest = fixture(Path(d))
            original = edge_path.read_text()
            edge_path.write_text(original.replace(",50,1,0,", ",50,999,0,"))
            with self.assertRaisesRegex(ValueError, "Out-of-range native M9 edge"):
                run(m7, grouped, unlinked, edge_path, dest)

    def test_m7_missing_unlinked_export_report_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            m7, grouped, unlinked, edge_path, dest = fixture(Path(d))
            (unlinked / "unlinked_text_export_report.json").write_text(json.dumps({
                "tables_exported": 0, "table_entries": [], "full_game_coverage": "NOT_CLAIMED"
            }))
            with self.assertRaisesRegex(ValueError, "unlinked text export report"):
                run(m7, grouped, unlinked, edge_path, dest)


if __name__ == "__main__":
    unittest.main()
