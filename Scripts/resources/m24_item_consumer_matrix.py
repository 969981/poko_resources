#!/usr/bin/env python3
"""Rebuild read-only item consumer matrix from verified M12/M20 original reports.

M24 DOES NOT prove gameplay names, 00983 loader or runtime V2 method identity.
No original ROM/ExeFS/PNG file is changed. Input reports are already native-
instruction-derived artifacts, not substituted synthetic sources.
"""
from __future__ import annotations
import argparse
import csv
import json
import hashlib
import struct
from pathlib import Path

ROOT = Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS")
M12 = ROOT / "M12/item_id_lookup_0x26_original_evidence.json"
M20 = ROOT / "M20/m20_two_stage_item_callers.json"
M201 = ROOT / "M20/m20_1_original_wrapper_caller_offsets.csv"
OUT = ROOT / "M24"
MAIN_SHA = "8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ITEM_SHA = "2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
ITEM_BINARY = Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
BASELINE_IDS = (6, 101, 302)
ANCHORS = {
    "0xe5aa60": "#0x26",
    "0x10289f4": "#0x26",
    "0x1028a38": "#0x39",
    "0xabbb64": "#0x3a",
    "0xabbbd4": "#0x3a",
}
COLS = ("caller_pc", "calls_original_wrapper", "wrapper_plus8_in_bounded_window",
        "post_call_field_accesses", "post_call_instructions_scanned",
        "original_main_sha256", "gameplay_context", "item_loader_proven",
        "field_semantics_proven", "evidence_grade")


def build(m12: dict, m20: dict, rows: list[dict]) -> tuple[list[dict], dict]:
    if not (m12.get("source_main_sha256") == m20.get("original_main_sha256") == MAIN_SHA and
            m12.get("source_item_sha256") == m20.get("original_item_sha256") == ITEM_SHA):
        raise ValueError("M24_ORIGINAL_SOURCE_HASH_MISMATCH")
    if (m20.get("two_stage_wrapper_pc") != "0x2f1f0" or
            m20.get("direct_BL_callers_total") != 17 or
            len(m20.get("direct_BL_callers", [])) != 17 or
            len(rows) != 17 or
            len(m20.get("caller_instruction_windows", [])) != 17):
        raise ValueError("M24_CALLER_SCOPE_UNEXPECTED")
    if (m12.get("proven_00983_loader") is not False or
            m12.get("enum_definition_proven") is not False or
            m20.get("returned_record_to_00983_verified") is not False):
        raise ValueError("M24_INPUT_PROVENANCE_STATE_CHANGED_REVIEW_REQUIRED")
    m12_ins = {r["pc"].lower(): r["instruction"].lower()
               for r in m12.get("matched_original_instructions", [])}
    for pc, offset in ANCHORS.items():
        if pc not in m12_ins or not m12_ins[pc].startswith("ldrb ") or offset not in m12_ins[pc]:
            raise ValueError("M24_FIELD_ANCHOR_CHANGED_" + pc)
    callers = set(m20["direct_BL_callers"])
    instructions = {r["caller_pc"]: r["instructions"]
                    for r in m20["caller_instruction_windows"]}
    if set(instructions) != callers or {r["caller_pc"] for r in rows} != callers:
        raise ValueError("M24_CALLER_SET_DISAGREES")
    report = []
    for r in sorted(rows, key=lambda x: int(x["caller_pc"], 16)):
        pc = r["caller_pc"]
        if not any(v["pc"] == pc and v["asm"].lower() == "bl #0x2f1f0"
                   for v in instructions[pc]):
            raise ValueError("M24_DIRECT_BL_NOT_VALIDATED_" + pc)
        if r["original_exefs_sha256"] != MAIN_SHA:
            raise ValueError("M24_M201_SHA_MISMATCH_" + pc)
        report.append({
            "caller_pc": pc,
            "calls_original_wrapper": "1",
            "wrapper_plus8_in_bounded_window": r["has_return_wrapper_plus8"],
            "post_call_field_accesses": r["post_call_offset_accesses"],
            "post_call_instructions_scanned": r["post_call_instructions_scanned"],
            "original_main_sha256": MAIN_SHA,
            "gameplay_context": "UNKNOWN",
            "item_loader_proven": "0",
            "field_semantics_proven": "0",
            "evidence_grade": "M20_BOUNDED_INSTRUCTION_WINDOW_DATAFLOW_UNPROVEN",
        })
    offsets = {}
    for row in report:
        for field in ("0x41", "0xc", "0x1e", "0x18", "0x3a", "0x27", "0x14"):
            if ("#"+field) in row["post_call_field_accesses"]:
                offsets[field] = offsets.get(field, 0) + 1
    summary = {
        "stage": "M24_STATIC_WRAPPER_CALLER_MATRIX",
        "source_main_sha256": MAIN_SHA,
        "source_item_sha256": ITEM_SHA,
        "original_wrapper_pc": "0x2f1f0",
        "direct_BL_callers": len(report),
        "wrapper_plus8_in_bounded_window": sum(x["wrapper_plus8_in_bounded_window"] == "1" for x in report),
        "rows_with_nearby_post_call_field_access":
            sum(bool(x["post_call_field_accesses"]) for x in report),
        "field_offset_nearby_counts": dict(sorted(offsets.items())),
        "independent_M12_field_read_sites": dict(ANCHORS),
        "nearby_wrapper_callers_with_0x26_read":
            sum("#0x26" in x["post_call_field_accesses"] for x in report),
        "dynamic_v1_method_known": False,
        "dynamic_v2_method_known": False,
        "runtime_three_complete_68byte_records_verified": False,
        "official_item_kind_enum_proven": False,
        "inventory_construction_material_context_proven": False,
        "warning": ("These 12-instruction windows are candidate reads only; "
                    "they do not bind source pointer to 00983.bin or verify UI usage.")
    }
    return report, summary


def exact_original_baselines(item_path: Path) -> list[dict]:
    blob = item_path.read_bytes()
    if (hashlib.sha256(blob).hexdigest() != ITEM_SHA or
            len(blob) != 64 + 4600*68 or
            struct.unpack_from("<II", blob) != (4600, 3)):
        raise ValueError("M24_ORIGINAL_ITEM_TABLE_SHA_OR_HEADER_MISMATCH")
    rows = []
    for item_id in BASELINE_IDS:
        at = 64 + item_id*68
        record = blob[at:at+68]
        if len(record) != 68:
            raise ValueError("M24_TRUNCATED_SOURCE_BASELINE")
        name_index = struct.unpack_from("<H", record, 0x22)[0]
        if not name_index:
            raise ValueError("M24_EMPTY_SOURCE_ITEM_SAMPLE")
        rows.append({
            "item_id": item_id, "file_offset_dec": at, "file_offset_hex": hex(at),
            "name_index_u16": name_index,
            "kind_26_u8": record[0x26], "group_39_u8": record[0x39],
            "group_3a_u8": record[0x3a],
            "source_68byte_sha256": hashlib.sha256(record).hexdigest(),
            "source_68byte_hex": record.hex(),
            "source_file_sha256": ITEM_SHA,
            "runtime_full_68byte_match": "NOT_COLLECTED",
            "evidence": "ORIGINAL_00983_SOURCE_BYTES_ONLY",
        })
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--m12", type=Path, default=M12)
    p.add_argument("--m20", type=Path, default=M20)
    p.add_argument("--m20-caller-csv", type=Path, default=M201)
    p.add_argument("--out", type=Path, default=OUT)
    p.add_argument("--original-item-table", type=Path, default=ITEM_BINARY)
    args = p.parse_args()
    m12 = json.loads(args.m12.read_text(encoding="utf-8"))
    m20 = json.loads(args.m20.read_text(encoding="utf-8"))
    with args.m20_caller_csv.open(encoding="utf-8-sig", newline="") as f:
        source = list(csv.DictReader(f))
    rows, summary = build(m12, m20, source)
    args.out.mkdir(parents=True, exist_ok=True)
    with (args.out / "m24_wrapper_consumer_matrix.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLS)
        writer.writeheader()
        writer.writerows(rows)
    baselines = exact_original_baselines(args.original_item_table)
    with (args.out / "m24_three_original_68byte_baselines.csv").open(
            "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(baselines[0]))
        writer.writeheader()
        writer.writerows(baselines)
    (args.out / "m24_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
