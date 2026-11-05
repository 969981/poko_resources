#!/usr/bin/env python3
"""Export M7 PARSED native text tables not present in any nine-language group.

The absence of a nine-language match does NOT establish a table's language or
usage. All exports use language=UNKNOWN and category=UNKNOWN. No game files are
modified, and every source is checked against the M7 native inventory SHA-256.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

try:
    from .export_native_text_files import (
        digest, load_groups, load_inventory, txt_escape,
    )
    from .recover_native_text_ids import parse
except ImportError:
    from export_native_text_files import (
        digest, load_groups, load_inventory, txt_escape,
    )
    from recover_native_text_ids import parse


def unlinked_entries(groups_csv: Path, inventory_csv: Path) -> dict[int, dict]:
    groups = load_groups(groups_csv, None)
    linked = {
        entry for group in groups
        for entry in range(int(group["start_entry"]), int(group["start_entry"]) + 9)
    }
    inventory = load_inventory(inventory_csv)
    if any(entry not in inventory or inventory[entry]["status"] != "PARSED" for entry in linked):
        raise ValueError("M7 nine-language group has a missing/non-PARSED inventory entry")
    return {
        entry: row for entry, row in sorted(inventory.items())
        if row["status"] == "PARSED" and entry not in linked
    }


def export_entry(entry: int, reference: dict, decoded: Path, dest: Path) -> dict:
    original = decoded / f"{entry:05d}.bin"
    data = original.read_bytes()
    sha = digest(data)
    if sha != reference["sha256"] or len(data) != int(reference["bytes"]):
        raise ValueError(f"M7 source SHA/size mismatch: {entry}")
    table, status = parse(data, entry, original.as_posix())
    if status != "PARSED" or table is None:
        raise ValueError(f"M7 native parser rejected {original}: {status}")
    if (table.count != int(reference["record_count"]) or
            table.width != int(reference["record_width"])):
        raise ValueError(f"M7 native shape mismatch: {entry}")
    if table.sha != sha:
        raise ValueError(f"M7 native parser hash mismatch: {entry}")

    out = dest / f"table_{entry:05d}"
    out.mkdir(parents=True, exist_ok=True)
    lines = [txt_escape(values[0]) for values, _, _ in table.rows]
    txt = ("\n".join(lines) + "\n").encode("utf-8")
    txt_path = out / "unknown.txt"
    txt_path.write_bytes(txt)

    forms_path = out / "unknown.forms.jsonl"
    with forms_path.open("w", encoding="utf-8", newline="\n") as f:
        for text_id, (values, offsets, metadata) in enumerate(table.rows):
            f.write(json.dumps({
                "text_id": text_id,
                "forms": list(values),
                "absolute_byte_offsets": list(offsets),
                "raw_metadata_u32": list(metadata),
            }, ensure_ascii=False, separators=(",", ":")) + "\n")

    manifest = {
        "entry": entry,
        "language": "UNKNOWN",
        "category": "UNKNOWN",
        "evidence_grade": "UNLINKED_NATIVE_RECORD",
        "text_id_semantics": "ZERO_BASED_NATIVE_TABLE_RECORD_ORDINAL",
        "record_count": table.count,
        "record_width": table.width,
        "forms_per_record": table.forms,
        "header_version_raw_u32": table.version,
        "source": {
            "path": table.path,
            "sha256": sha,
            "bytes": len(data),
        },
        "outputs": {
            "txt": txt_path.name,
            "txt_sha256": digest(txt),
            "all_forms_jsonl": forms_path.name,
            "all_forms_jsonl_sha256": digest(forms_path.read_bytes()),
            "lines": table.count,
        },
        "notes": [
            "No confirmed language, nine-language alignment, or game caller relation.",
            "TXT: one physical line per native record, only form index zero.",
            "TXT retains game tags but escapes physical LF, CR, TAB, backslash.",
            "JSONL retains all native forms, exact text, offsets and u32 metadata.",
        ],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "entry": entry, "record_count": table.count,
        "record_width": table.width, "forms": table.forms,
        "source_sha256": sha,
        "directory": out.as_posix(),
        "language": "UNKNOWN", "category": "UNKNOWN",
    }


def run(decoded: Path, groups_csv: Path, inventory_csv: Path, dest: Path,
        selected: set[int] | None = None) -> dict:
    candidates = unlinked_entries(groups_csv, inventory_csv)
    if selected is not None:
        missing = selected - set(candidates)
        if missing:
            raise ValueError(f"Unlinked M7 entries missing: {sorted(missing)}")
        candidates = {e: row for e, row in candidates.items() if e in selected}
    dest.mkdir(parents=True, exist_ok=True)
    results = [export_entry(e, row, decoded, dest) for e, row in candidates.items()]
    if selected is None:
        expected_dirs = {f"table_{entry:05d}" for entry in candidates}
        for p in dest.glob("table_*"):
            if p.is_dir() and p.name not in expected_dirs:
                shutil.rmtree(p)
    report = {
        "status": "UNLINKED_NATIVE_TEXT_EXPORTED_WITH_M7_PROVENANCE",
        "source": "Pokopia 2.0.1 decoded LINKDATA / M7",
        "language": "UNKNOWN",
        "category": "UNKNOWN",
        "evidence_grade": "UNLINKED_NATIVE_RECORD",
        "tables_exported": len(results),
        "native_records": sum(x["record_count"] for x in results),
        "native_record_form_slots": sum(x["record_count"] * x["forms"] for x in results),
        "table_entries": results,
        "full_game_coverage": "NOT_CLAIMED",
        "notes": [
            "These tables are excluded from M7's identified 195 nine-language groups.",
            "Do not interpret UNKNOWN as a specific locale or feature category.",
            "Unparsed/other-layout LINKDATA inputs are out of scope.",
        ],
    }
    (dest / "unlinked_text_export_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    base = Path("UnPack/2.0.1")
    ap.add_argument("--decoded-root", type=Path, default=base / "romfs/LD_C0_R.BIN/decoded")
    ap.add_argument("--groups", type=Path, default=base / "Resources/Localization/M7/nine_language_groups.csv")
    ap.add_argument("--inventory", type=Path, default=base / "Resources/Localization/M7/native_table_inventory.csv")
    ap.add_argument("--dest", type=Path, default=base / "Resources/Localization/UnlinkedText")
    ap.add_argument("--start-entry", type=int, action="append",
                    help="Optional native entries to export; default: every unlinked PARSED table")
    args = ap.parse_args()
    selected = set(args.start_entry) if args.start_entry else None
    report = run(args.decoded_root, args.groups, args.inventory, args.dest, selected)
    print(json.dumps({
        "status": report["status"],
        "tables_exported": report["tables_exported"],
        "native_records": report["native_records"],
        "native_record_form_slots": report["native_record_form_slots"],
        "output_root": str(args.dest),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
