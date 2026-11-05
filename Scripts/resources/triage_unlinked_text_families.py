#!/usr/bin/env python3
"""M7.1: Native-only triage of nine-language hypotheses among unlinked text.

Read the *original* Pokopia 2.0.1 decoded LINKDATA bytes; never infer a locale
or a game caller from adjacency alone. Proven M8 role tables are reported as
positive controls but are not redefined by candidate scores.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

try:
    from .export_native_text_files import load_groups, load_inventory
    from .recover_native_text_ids import LANGS, parse, witness
except ImportError:
    from export_native_text_files import load_groups, load_inventory
    from recover_native_text_ids import LANGS, parse, witness


def write_csv(path: Path, rows: list[dict], headers: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def m8_positive_controls(path: Path, inventory: dict[int, dict]) -> dict[int, str]:
    """Read-only: trust only the explicitly pinned M8 role mapping with full row/locale coverage."""
    controls: dict[int, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            start = int(row["target_group_start"])
            if (row["relationship"] != "explicit_native_role_table" or
                    row["evidence_grade"] != "PINNED_PARSER_ROLE_PLUS_NATIVE_ROW" or
                    row["category"] not in ("Reactions", "Skills")):
                raise ValueError(f"Not a pinned M8 native role table: {start}")
            count = int(inventory[start]["record_count"])
            if not (0 <= int(row["target_text_id"]) < count and int(row["target_form_index"]) == 0):
                raise ValueError(f"M8 role row out of bounds: {start}")
            control = controls.setdefault(start, {
                "category": row["category"], "parser": row["parser_source_url"],
                "count": count, "rows": set()
            })
            if (control["category"] != row["category"] or
                    control["parser"] != row["parser_source_url"]):
                raise ValueError(f"M8 role-table identity disagreement: {start}")
            control["rows"].add(int(row["target_text_id"]))
            for offset, lang in enumerate(LANGS):
                entry = start + offset
                inv = inventory.get(entry)
                if (int(row[lang + "_entry"]) != entry or not inv or
                        inv["status"] != "PARSED" or
                        int(inv["record_count"]) != count or
                        int(inv["record_width"]) != 8):
                    raise ValueError(f"M8 role language/source mismatch: {start}:{lang}")
    for start, data in controls.items():
        if data["rows"] != set(range(data["count"])):
            raise ValueError(f"Partial M8 role row coverage: {start}")
    return {start: data["category"] for start, data in controls.items()}


def runs_from(tables: dict[int, object]) -> list[list[int]]:
    """Maximal contiguous runs with identical native shape and nonempty bitmap, ignoring flags."""
    ids = sorted(tables)
    if not ids:
        return []
    runs, current = [], [ids[0]]
    for entry in ids[1:]:
        previous, first = current[-1], current[0]
        x, y = tables[entry], tables[first]
        if (entry == previous + 1 and x.count == y.count and
                x.width == y.width and x.bitmap == y.bitmap):
            current.append(entry)
        else:
            runs.append(current)
            current = [entry]
    runs.append(current)
    return runs


def classify_group(chunk: list[int], run_length: int, tables: dict[int, object],
                   controls: dict[int, str]) -> tuple[str, dict]:
    start = chunk[0]
    stats = {
        "jp_kana": witness(tables[chunk[0]], "kana"),
        "ko_hangul": witness(tables[chunk[7]], "hangul"),
        "zht_han": witness(tables[chunk[6]], "han"),
        "zhs_han": witness(tables[chunk[8]], "han"),
    }
    positive = all(stats.values())
    content_count = tables[start].nonempty
    if start in controls:
        grade = "M8_PINNED_NATIVE_ROLE_TABLE"
    elif run_length > 9:
        grade = "AMBIGUOUS_MULTI_GROUP_RUN_NOT_VERIFIED"
    elif content_count < 2:
        grade = "LOW_CONTENT_NOT_VERIFIED"
    elif positive:
        grade = "STRUCTURE_AND_SCRIPT_HYPOTHESIS_NOT_VERIFIED"
    else:
        grade = "STRUCTURE_ONLY_HYPOTHESIS_NOT_VERIFIED"
    return grade, stats


def run(decoded: Path, groups_csv: Path, inventory_csv: Path,
        m8_roles: Path, dest: Path) -> dict:
    inventory = load_inventory(inventory_csv)
    grouped = load_groups(groups_csv, None)
    linked = {int(g["start_entry"]) + offset for g in grouped for offset in range(9)}
    if any(i not in inventory or inventory[i]["status"] != "PARSED" for i in linked):
        raise ValueError("M7 group references a missing/non-PARSED table")
    unlinked = sorted(entry for entry, row in inventory.items()
                      if row["status"] == "PARSED" and entry not in linked)
    controls = m8_positive_controls(m8_roles, inventory)
    if any(i in linked or i not in unlinked for start in controls for i in range(start, start + 9)):
        raise ValueError("M8 control is not entirely inside the M7 unlinked source set")

    tables = {}
    for entry in unlinked:
        ref = inventory[entry]
        path = decoded / f"{entry:05d}.bin"
        data = path.read_bytes()
        if (hashlib.sha256(data).hexdigest() != ref["sha256"] or
                len(data) != int(ref["bytes"])):
            raise ValueError(f"Native M7 inventory hash/size mismatch: {entry}")
        table, status = parse(data, entry, path.as_posix())
        if status != "PARSED" or table is None:
            raise ValueError(f"Native M7 table parsing changed: {entry} -> {status}")
        if (table.count != int(ref["record_count"]) or
                table.width != int(ref["record_width"]) or
                table.nonempty != int(ref["nonempty_rows"]) or
                table.bitmap != ref["bitmap_sha256"] or
                table.flaghash != ref["metadata_sha256"]):
            raise ValueError(f"Native M7 structural provenance mismatch: {entry}")
        tables[entry] = table

    runs = runs_from(tables)
    run_rows, candidate_rows = [], []
    covered = set()
    grade_count = Counter()
    for entries in runs:
        start, end, length = entries[0], entries[-1], len(entries)
        first = tables[start]
        flags = len({tables[e].flaghash for e in entries})
        can_segment = length >= 9 and length % 9 == 0
        run_rows.append({
            "run_start_entry": start, "run_end_entry": end, "run_file_count": length,
            "native_record_count": first.count, "native_record_width": first.width,
            "native_nonempty_record_count": first.nonempty,
            "nonempty_bitmap_sha256": first.bitmap,
            "metadata_hash_variant_count": flags,
            "hypothetical_nine_chunks": length // 9 if can_segment else 0,
            "boundary_status": (
                "EXACT_NINE_RUN" if length == 9 else
                "AMBIGUOUS_MULTI_NINE_RUN" if can_segment else
                "NO_COMPLETE_NINE_GROUP"
            ),
            "language_identity": "NOT_INFERRED_FROM_RUN_STRUCTURE",
            "script_caller_verified": "false",
        })
        if not can_segment:
            continue
        for index in range(0, length, 9):
            chunk = entries[index:index+9]
            grade, script = classify_group(chunk, length, tables, controls)
            grade_count[grade] += 1
            covered.update(chunk)
            candidate_rows.append({
                "hypothetical_start_entry": chunk[0],
                "hypothetical_end_entry": chunk[-1],
                "parent_run_start": start,
                "parent_run_length": length,
                "nine_chunk_index_zero_based": index // 9,
                "original_boundary_uniquely_supported": "true" if length == 9 else "false",
                "native_record_count": first.count,
                "native_width": first.width,
                "native_nonempty_records": first.nonempty,
                "metadata_hash_variants_within_chunk": len({tables[e].flaghash for e in chunk}),
                "structural_bitmap_sha256": first.bitmap,
                **script,
                "positive_script_order_witness": str(all(script.values())).lower(),
                "hypothesis_grade": grade,
                "m8_pinned_role": controls.get(chunk[0], ""),
                "locale_order_hypothesis": ",".join(LANGS),
                "actual_locale_assignment": "M8_PINNED" if chunk[0] in controls else "UNVERIFIED",
                "native_source_entries_json": json.dumps(chunk),
                "native_source_sha256_json": json.dumps([tables[e].sha for e in chunk]),
                "script_caller_verified": "false",
                "semantic_category": controls.get(chunk[0], "UNKNOWN"),
            })
    missing_controls = set(controls) - {
        row["hypothetical_start_entry"] for row in candidate_rows
        if row["m8_pinned_role"]
    }
    if missing_controls:
        raise ValueError(f"M8 pinned positive controls not found at native run boundaries: {sorted(missing_controls)}")

    unsegmented = sorted(set(unlinked) - covered)
    unmatched = [{
        "source_entry": entry,
        "source_sha256": tables[entry].sha,
        "native_record_count": tables[entry].count,
        "native_record_width": tables[entry].width,
        "nonempty_records": tables[entry].nonempty,
        "language": "UNKNOWN",
        "category": "UNKNOWN",
        "caller_verified": "false",
    } for entry in unsegmented]
    report = {
        "status": "M7_UNLINKED_NATIVE_STRUCTURE_AND_SCRIPT_TRIAGE_NOT_NEW_VERIFIED_MAPPING",
        "native_unlinked_tables_scanned": len(unlinked),
        "original_source_sha256_verified": len(tables),
        "m7_linked_tables_excluded": len(linked),
        "m8_pinned_role_positive_controls": controls,
        "m8_pinned_source_files": len(controls) * 9,
        "remaining_without_m8_role_identity": len(unlinked) - len(controls) * 9,
        "maximal_shape_bitmap_runs": len(runs),
        "runs_nine_or_more_and_divisible_by_nine": sum(r["hypothetical_nine_chunks"] > 0 for r in run_rows),
        "exactly_nine_runs": sum(r["run_file_count"] == 9 for r in run_rows),
        "runs_longer_than_nine_divisible_by_nine": sum(r["run_file_count"] > 9 and r["hypothetical_nine_chunks"] > 0 for r in run_rows),
        "source_files_in_nine_chunk_runs": len(covered),
        "source_files_outside_nine_chunk_runs": len(unsegmented),
        "hypothetical_nine_chunks": len(candidate_rows),
        "hypothesis_grades": dict(sorted(grade_count.items())),
        "new_verified_locale_assignments": 0,
        "new_verified_semantic_categories": 0,
        "new_verified_script_callers": 0,
        "warnings": [
            "Same count/stride/nonempty bitmap is structural evidence, not proof of locale.",
            "M7 anchors and M8 pinned role tables are positive controls only.",
            "Chunk boundaries in >9-length runs are arbitrary and must not be promoted.",
            "Unicode script witnesses provide prioritization, not definitive locale or narrative identity.",
            "All native files were matched to the M7 SHA-256 inventory before analysis.",
        ],
    }
    dest.mkdir(parents=True, exist_ok=True)
    write_csv(dest / "unlinked_native_shape_runs.csv", run_rows,
              list(run_rows[0]) if run_rows else ["run_start_entry"])
    write_csv(dest / "nine_language_hypotheses_NOT_VERIFIED.csv", candidate_rows,
              list(candidate_rows[0]) if candidate_rows else ["hypothetical_start_entry"])
    write_csv(dest / "unsegmented_native_text_tables.csv", unmatched,
              list(unmatched[0]) if unmatched else ["source_entry"])
    (dest / "native_text_families_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    base = Path("UnPack/2.0.1")
    ap.add_argument("--decoded-root", type=Path,
                    default=base / "romfs/LD_C0_R.BIN/decoded")
    ap.add_argument("--groups", type=Path,
                    default=base / "Resources/Localization/M7/nine_language_groups.csv")
    ap.add_argument("--inventory", type=Path,
                    default=base / "Resources/Localization/M7/native_table_inventory.csv")
    ap.add_argument("--m8-roles", type=Path,
                    default=base / "Resources/Localization/M8/native_role_text_refs.csv")
    ap.add_argument("--dest", type=Path,
                    default=base / "Resources/Localization/TextFamilies")
    args = ap.parse_args()
    print(json.dumps(run(args.decoded_root, args.groups, args.inventory,
                         args.m8_roles, args.dest), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
