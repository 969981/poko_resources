#!/usr/bin/env python3
"""Read-only M23 GDB JSONL audit; exact per-ID source bytes, no inferred enums."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import struct
from pathlib import Path

MAIN_SHA = "8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ITEM_SHA = "2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
SCHEMA = "M23_ITEM_CLASSIFICATION_GDB_V1"
SOURCE = Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
COUNT, HEADER, STRIDE = 4600, 64, 68
FIELD_EVENTS = {"field_26_loop_a", "field_26_loop_b", "field_3a_predicate"}


def verified_source(path):
    b = Path(path).read_bytes()
    if (len(b) != HEADER+COUNT*STRIDE or
        struct.unpack_from("<II", b) != (COUNT, 3) or
        hashlib.sha256(b).hexdigest() != ITEM_SHA):
        raise ValueError("M23_ORIGINAL_00983_SOURCE_IDENTITY_FAILURE")
    return b


def audit(events, source, min_distinct=3):
    if not events or events[0].get("event") != "session":
        raise ValueError("M23_MISSING_SESSION_HEADER")
    head = events[0]
    if (head.get("schema") != SCHEMA or
        head.get("source_main_file_sha256") != MAIN_SHA or
        head.get("source_item_table_sha256") != ITEM_SHA or
        head.get("main_executable_mapped_identity_verified") is not False):
        raise ValueError("M23_LOG_SOURCE_IDENTITY_MISMATCH")
    kinds = Counter()
    matched_ids, raw_16_ids, other_ids, pointers, consumer_sites = (set() for _ in range(5))
    v1_targets, v2_targets = set(), set()
    v1_verified_targets, v2_verified_targets = set(), set()
    phase_counts, phase_matched_ids, phase_consumer_sites = Counter(), {}, {}
    phase_stacks = {}
    errors, discrepancies = [], []
    for lineno, row in enumerate(events[1:], 2):
        if row.get("schema") != SCHEMA:
            raise ValueError(f"M23_SCHEMA_INVALID_LINE_{lineno}")
        k = row.get("event")
        kinds[k] += 1
        phase = str(row.get("phase") or "unlabeled")
        if phase not in {"unlabeled", "inventory", "crafting", "construction", "materials"}:
            errors.append({"line": lineno, "reason": "INVALID_OPERATOR_PHASE"})
            phase = "unlabeled"
        if k in FIELD_EVENTS:
            phase_counts[phase] += 1
        if k == "v1_call":
            if row.get("v1_method"):
                v1_targets.add(row["v1_method"])
                if (row.get("v1_vtable_slot_agrees") is True and
                    row.get("v1_method_from_vtable_slot") == row["v1_method"]):
                    v1_verified_targets.add(row["v1_method"])
        if k == "v2_tailcall":
            if row.get("v2_method"):
                v2_targets.add(row["v2_method"])
                if (row.get("v2_vtable_slot_agrees") is True and
                    row.get("v2_method_from_vtable_slot") == row["v2_method"]):
                    v2_verified_targets.add(row["v2_method"])
        if k not in FIELD_EVENTS:
            continue
        i = row.get("item_id")
        if row.get("status") == "READ_ERROR":
            errors.append({"line": lineno, "reason": row.get("reason", "")})
            continue
        if not isinstance(i, int) or not 0 < i < COUNT:
            errors.append({"line": lineno, "reason": "invalid item id"})
            continue
        try:
            mem = bytes.fromhex(row.get("runtime_record_hex", ""))
        except (ValueError, TypeError):
            mem = b""
        if len(mem) != STRIDE:
            errors.append({"line": lineno, "reason": "runtime record not 68 bytes"})
            continue
        original = source[HEADER+i*STRIDE:HEADER+(i+1)*STRIDE]
        equal = (mem == original and
                 row.get("source_record_sha256") == hashlib.sha256(original).hexdigest() and
                 row.get("runtime_record_sha256") == hashlib.sha256(mem).hexdigest() and
                 row.get("source_raw_kind_u8") == original[0x26] and
                 row.get("runtime_raw_kind_u8") == mem[0x26] and
                 row.get("status") == "FULL_68_BYTE_MATCH")
        if equal and struct.unpack_from("<H", original, 0x22)[0] > 0:
            matched_ids.add(i)
            phase_matched_ids.setdefault(phase, set()).add(i)
            phase_consumer_sites.setdefault(phase, set()).add(k)
            stack = row.get("guest_call_stack") or []
            if isinstance(stack, list):
                pcs = [x.get("candidate_main_rva") for x in stack[:8]
                       if isinstance(x, dict) and isinstance(x.get("candidate_main_rva"), str)]
                if pcs:
                    phase_stacks.setdefault(phase, set()).add(tuple(pcs))

            (raw_16_ids if original[0x26] == 0x10 else other_ids).add(i)
            pointers.add(row.get("record_ptr"))
            consumer_sites.add(k)
        else:
            discrepancies.append({"line": lineno, "item_id": i,
                                  "diff_bytes": sum(a != b for a,b in zip(mem,original))})
    sufficient = (len(matched_ids) >= min_distinct and
                  bool(raw_16_ids) and bool(other_ids) and
                  len(pointers) >= min_distinct)
    return {
        "status": ("RUNTIME_68B_RECORD_IDENTITY_SUPPORTED__LOADER_UNPROVEN"
                   if sufficient else "INSUFFICIENT_RUNTIME_RECORD_EVIDENCE"),
        "events": dict(kinds),
        "distinct_full_match_ids": len(matched_ids),
        "full_match_ids": sorted(matched_ids),
        "raw_kind_0x10_full_match_ids": sorted(raw_16_ids),
        "other_raw_kind_full_match_ids": sorted(other_ids),
        "distinct_runtime_record_pointers": len(pointers),
        "matched_consumer_sites": sorted(consumer_sites),
        "dynamic_v1_targets": sorted(v1_targets),
        "dynamic_v2_targets": sorted(v2_targets),
        "v1_targets_correlated_with_real_vtable_slot": sorted(v1_verified_targets),
        "v2_targets_correlated_with_real_vtable_slot": sorted(v2_verified_targets),
        "operator_declared_phase_event_counts": dict(phase_counts),
        "operator_declared_phase_matching_ids":
            {k: sorted(v) for k,v in sorted(phase_matched_ids.items())},
        "operator_declared_phase_consumer_sites":
            {k: sorted(v) for k,v in sorted(phase_consumer_sites.items())},
        "operator_declared_phase_unique_call_stacks":
            {k: len(v) for k,v in sorted(phase_stacks.items())},
        "inventory_crafting_construction_material_semantics_proven": False,
        "read_errors": errors[:30],
        "mismatches": discrepancies[:30],
        "min_distinct_required": min_distinct,
        "exact_record_identity_criteria_met": sufficient,
        "original_00983_loader_proven": False,
        "official_item_kind_enum_proven": False,
        "per_item_max_stack_proven": False,
        "mapped_exefs_build_verified": False,
        "operator_phase_labels_are_game_verified": False,
        "warning": "Disk input hashes and user GDB logs do not independently attest the live game build, original loader or official enum names."
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--jsonl", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--min-distinct", type=int, default=3)
    args = parser.parse_args()
    if not 2 <= args.min_distinct <= 30:
        parser.error("min-distinct must be 2..30")
    data = verified_source(args.source)
    events = []
    for index, line in enumerate(args.jsonl.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"INVALID_JSONL_LINE_{index}") from exc
    result = audit(events, data, args.min_distinct)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print(result["status"], "matching item IDs:", result["full_match_ids"])


if __name__ == "__main__":
    main()
