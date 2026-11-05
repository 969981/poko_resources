#!/usr/bin/env python3
"""Build the conservative M7/M9 native text provenance catalog.

No new foreign keys are inferred. M9's already verified *typed resource* edges
are copied to a searchable row index without claiming script/runtime callers.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

try:
    from .export_native_text_files import LANGS, load_groups, load_inventory
except ImportError:
    from export_native_text_files import LANGS, load_groups, load_inventory


def csv_write(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(m7: Path, grouped_root: Path, unlinked_root: Path,
        m9_edges: Path, dest: Path) -> dict:
    inventory = load_inventory(m7 / "native_table_inventory.csv")
    parsed = {k: v for k, v in inventory.items() if v["status"] == "PARSED"}
    groups = load_groups(m7 / "nine_language_groups.csv", None)
    group_by_entry = {}
    group_by_start = {}
    for group in groups:
        start = int(group["start_entry"])
        group_by_start[start] = group
        for offset, lang in enumerate(LANGS):
            entry = start + offset
            if entry in group_by_entry:
                raise ValueError(f"Overlapping native M7 grouping: {entry}")
            group_by_entry[entry] = (start, lang, group["evidence_grade"])
    if not set(group_by_entry) <= set(parsed):
        raise ValueError("M7 linked native table absent from parsed inventory")
    unlinked = set(parsed) - set(group_by_entry)

    grouped_report = load_json(grouped_root / "text_export_report.json")
    unlinked_report = load_json(unlinked_root / "unlinked_text_export_report.json")
    if (grouped_report["groups_exported"] != len(groups) or
            {r["start_entry"] for r in grouped_report["table_groups"]} != set(group_by_start)):
        raise ValueError("M7 grouped text export report does not match source group CSV")
    if (unlinked_report["tables_exported"] != len(unlinked) or
            {r["entry"] for r in unlinked_report["table_entries"]} != unlinked):
        raise ValueError("M7 unlinked text export report does not match native inventory")
    if grouped_report["full_game_coverage"] != "NOT_CLAIMED" or unlinked_report["full_game_coverage"] != "NOT_CLAIMED":
        raise ValueError("Unexpected M7 output coverage status")

    table_rows = []
    for entry, source in sorted(parsed.items()):
        count, width = int(source["record_count"]), int(source["record_width"])
        if width not in (8, 32):
            raise ValueError(f"Unexpected native M7 record width: {entry}")
        is_grouped = entry in group_by_entry
        start, lang, grade = group_by_entry.get(entry, ("", "UNKNOWN", "UNLINKED_NATIVE_RECORD"))
        table_rows.append({
            "source_entry": entry,
            "source_sha256": source["sha256"],
            "record_count": count,
            "record_width": width,
            "forms_per_record": 1 if width == 8 else 6,
            "linkage": "NINE_LANGUAGE_CANDIDATE" if is_grouped else "UNLINKED_NATIVE_RECORD",
            "locale_candidate": lang if is_grouped else "UNKNOWN",
            "locale_status": "M7_STRUCTURAL_CANDIDATE" if is_grouped else "UNKNOWN",
            "group_start": start,
            "group_evidence_grade": grade,
            "business_category": "UNKNOWN",
            "export_directory": str((grouped_root / f"table_{start:05d}") if is_grouped
                                    else (unlinked_root / f"table_{entry:05d}")),
        })

    verified_rows = []
    group_domain_counts = Counter()
    group_unique_rows = defaultdict(set)
    with m9_edges.open(encoding="utf-8-sig", newline="") as f:
        edges = csv.DictReader(f)
        for edge in edges:
            start = int(edge["target_group_start"])
            if start not in group_by_start:
                raise ValueError(f"M9 verified edge points at unlinked/absent group: {start}")
            idx, form = int(edge["target_text_id"]), int(edge["target_form_index"])
            group = group_by_start[start]
            if not (0 <= idx < int(group["record_count"]) and
                    0 <= form < int(group["forms"])):
                raise ValueError(f"Out-of-range native M9 edge: group {start}, row {idx}, form {form}")
            if not edge["evidence_grade"] or not edge["source_domain"]:
                raise ValueError("M9 verified edge lacks evidence/domain")
            group_domain_counts[(start, edge["source_domain"], edge["category"], edge["evidence_grade"])] += 1
            group_unique_rows[start].add((idx, form))
            verified_rows.append({
                "edge_id": edge["edge_id"],
                "source_domain": edge["source_domain"],
                "source_record_id": edge["source_record_id"],
                "source_entry": edge["source_entry"],
                "source_field_offset": edge["source_field_offset"],
                "field_type": edge["field_type"],
                "target_group_start": start,
                "target_text_id": idx,
                "target_form_index": form,
                "category": edge["category"],
                "evidence_grade": edge["evidence_grade"],
                "parser_evidence": edge["parser_evidence"],
                "intermediates": edge["intermediates"],
                "target_export_directory": str(grouped_root / f"table_{start:05d}"),
                "script_caller_verified": "false",
            })
    group_rows = [{
        "target_group_start": start,
        "source_domain": domain,
        "category": category,
        "evidence_grade": evidence,
        "edge_count": n,
        "unique_group_text_rows_any_domain": len(group_unique_rows[start]),
    } for (start, domain, category, evidence), n in sorted(group_domain_counts.items())]
    if sum(int(r["edge_count"]) for r in group_rows) != len(verified_rows):
        raise AssertionError("Native row-edge accounting failed")

    dest.mkdir(parents=True, exist_ok=True)
    csv_write(dest / "native_text_table_catalog.csv", list(table_rows[0]), table_rows)
    if verified_rows:
        csv_write(dest / "m9_verified_text_row_links.csv", list(verified_rows[0]), verified_rows)
    if group_rows:
        csv_write(dest / "m9_verified_group_domain_summary.csv", list(group_rows[0]), group_rows)
    report = {
        "status": "M7_ALL_PARSED_TEXT_TABLES_CATALOGED_WITH_EXISTING_M9_TYPED_EDGES",
        "native_text_tables": len(parsed),
        "nine_language_candidate_groups": len(groups),
        "nine_language_source_tables": len(group_by_entry),
        "unlinked_native_text_tables": len(unlinked),
        "typed_resource_edges_from_m9": len(verified_rows),
        "m9_groups_with_verified_typed_edges": sorted(group_unique_rows),
        "m9_group_domains": [
            {"group_start": r["target_group_start"],
             "domain": r["source_domain"], "category": r["category"],
             "edges": r["edge_count"]} for r in group_rows
        ],
        "verified_new_script_to_text_caller_edges": 0,
        "unlinked_tables_with_m9_verified_typed_edges": 0,
        "full_game_coverage": "NOT_CLAIMED",
        "notes": [
            "Locale candidates are M7 structural assignments, not established locale identity for every table.",
            "M9 edges are existing typed resource/row relations, not newly proven script calls.",
            "A group's row-level verified edge is not evidence that the entire table has one category.",
            "No new Quest/Dialogue/Buildings/UI/Tutorials mappings were inferred.",
        ],
    }
    (dest / "native_text_catalog_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    base = Path("UnPack/2.0.1/Resources/Localization")
    ap.add_argument("--m7", type=Path, default=base / "M7")
    ap.add_argument("--grouped-root", type=Path, default=base / "TextExports")
    ap.add_argument("--unlinked-root", type=Path, default=base / "UnlinkedText")
    ap.add_argument("--m9-edges", type=Path,
                    default=base / "M9/verified_resource_text_edges.csv")
    ap.add_argument("--dest", type=Path, default=base / "TextCatalog")
    args = ap.parse_args()
    print(json.dumps(
        run(args.m7, args.grouped_root, args.unlinked_root, args.m9_edges, args.dest),
        indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
