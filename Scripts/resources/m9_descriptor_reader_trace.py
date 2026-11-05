#!/usr/bin/env python3
"""M9.7: find native references to descriptor enumeration function entries.

These functions write 24-byte descriptors into caller-supplied buffers.
BL, B, ADRP+ADD and 64-bit section literals are independently reported.
A reference to the writer is NOT a read of its output buffer, nor a
KIDSOBJDB field getter or M7 script/text foreign key.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_rnk_exefs_xrefs import decode_adrp, decode_add

ENTRIES = {
    "0x0b6e1578": 0xCA2C40,
    "0xe21ff09f": 0xD384C0,
    "0xf92c5190": 0xD59420,
}
EXPECTED_SHA = "8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
COLS = ("hash", "entry_pc", "site_pc", "section", "kind", "instruction_words",
        "target_pc", "evidence_grade", "runtime_reader_verified", "text_fk_verified")


def u32(data: bytes, at: int) -> int:
    return struct.unpack_from("<I", data, at)[0]


def branch_target(word: int, pc: int):
    opcode = word & 0xfc000000
    if opcode not in (0x94000000, 0x14000000):
        return None
    delta = word & 0x03ffffff
    if delta & (1 << 25):
        delta -= 1 << 26
    return ("BL_DIRECT" if opcode == 0x94000000 else "B_DIRECT", pc + delta * 4)


def scan_text(data: bytes, base: int, entries: dict, limit=500):
    reverse = {va: name for name, va in entries.items()}
    pages = {va >> 12 for va in reverse}
    hits = []
    seen = Counter()

    def emit(name, entry, pc, kind, words):
        if seen[(name, kind)] >= limit:
            return
        seen[(name, kind)] += 1
        hits.append({
            "hash": name, "entry_pc": entry, "site_pc": pc,
            "section": "text", "kind": kind, "instruction_words": words,
            "target_pc": entry, "evidence_grade": "NATIVE_STATIC_ENTRY_REFERENCE_ONLY",
            "runtime_reader_verified": False, "text_fk_verified": False,
        })

    for off in range(0, len(data)-3, 4):
        pc = base + off
        word = u32(data, off)
        branch = branch_target(word, pc)
        if branch is not None and branch[1] in reverse:
            name = reverse[branch[1]]
            emit(name, branch[1], pc, branch[0], [f"{word:08x}"])
        adrp = decode_adrp(word, pc)
        if adrp is None or (adrp[0] >> 12) not in pages:
            continue
        page, register = adrp
        # These are address construction candidates: do not propagate the
        # register across branches or assign a callee/consumer identity.
        for offset in (4, 8, 12, 16, 20, 24, 28, 32):
            nextoff = off + offset
            if nextoff + 4 > len(data):
                break
            other = u32(data, nextoff)
            add = decode_add(other)
            if not add or add[0] != register:
                continue
            target = page + add[2]
            if target in reverse:
                emit(reverse[target], target, pc, "ADRP_ADD_ADDRESS_CANDIDATE",
                     [f"{word:08x}", f"{other:08x}"])
    return hits


def scan_u64_literals(sections: list[dict], entries: dict, limit=100):
    reverse = {va: name for name, va in entries.items()}
    hits = []
    for part in sections:
        if part["name"] not in ("rodata", "data"):
            continue
        count = Counter()
        blob = part["data"]
        for off in range(0, len(blob)-7, 8):
            value = struct.unpack_from("<Q", blob, off)[0]
            if value not in reverse or count[value] >= limit:
                continue
            count[value] += 1
            hits.append({
                "hash": reverse[value], "entry_pc": value,
                "site_pc": part["mem_offset"] + off,
                "section": part["name"], "kind": "U64_LITERAL_ADDRESS_CANDIDATE",
                "instruction_words": [blob[off:off+8].hex()],
                "target_pc": value, "evidence_grade": "NATIVE_STATIC_ENTRY_REFERENCE_ONLY",
                "runtime_reader_verified": False, "text_fk_verified": False,
            })
    return hits


def analyze(main: bytes, writers: dict):
    digest = hashlib.sha256(main).hexdigest()
    if digest != EXPECTED_SHA or digest != writers.get("main_sha256"):
        raise ValueError("Original ExeFS NSO sha256 mismatch")
    kind, parts = get_sections(main)
    if kind != "NSO0":
        raise ValueError("Not original NSO0")
    text = next(x for x in parts if x["name"] == "text")
    records = {x["hash"]: x for x in writers["records"]}
    if set(records) != set(ENTRIES):
        raise ValueError("Unexpected M9.5 writer hash identities")
    for name, entry in ENTRIES.items():
        native = text["data"]
        off = entry - text["mem_offset"]
        if off < 0 or off + 4 > len(native):
            raise ValueError("Descriptor entry out of text bounds")
        # CBZ W2, <nonzero> -- verified first instruction for this exact build.
        word = u32(native, off)
        if (word & 0x7f00001f) != 0x34000002:
            raise ValueError(f"Entry instruction drift for {name}: {word:08x}")
        if not records[name]["adjacent_descriptor_pair_proven"]:
            raise ValueError("Original writer's pair evidence disappeared")
        if records[name]["movz_pc"] <= entry:
            raise ValueError("Descriptor entry/constructor order invalid")
    hits = scan_text(text["data"], text["mem_offset"], ENTRIES)
    hits += scan_u64_literals(parts, ENTRIES)
    hits.sort(key=lambda x: (x["hash"], x["section"], x["site_pc"], x["kind"]))
    grade = Counter(x["kind"] for x in hits)
    report = {
        "status": "M9_DESCRIPTOR_ENTRY_REFERENCE_TRIAGE_ONLY",
        "original_exefs_sha256": digest,
        "entry_functions": [
            {
                "hash": name, "entry_pc": entry,
                "writer_pc": records[name]["movz_pc"],
                "descriptor_record_stride_bytes": 24,
                "entry_parameter_2_is_count_candidate": True,
                "destination_buffer_is_x1_candidate": True,
                "verified_function_reader": False,
                "verified_KIDSOBJDB_getter": False,
            }
            for name, entry in ENTRIES.items()
        ],
        "xref_total": len(hits),
        "xref_by_kind": dict(grade),
        "verified_descriptor_buffer_readers": 0,
        "verified_kidsobjdb_property_getters": 0,
        "new_script_scene_quest_building_text_foreign_keys": 0,
        "limitations": [
            "BL/B are exact code-flow references, not proof the callee's output is read by the caller.",
            "ADRP+ADD only constructs an entry address and may not survive register clobbering.",
            "U64 literal candidates do not include relocation-dependent function pointers.",
            "Indirect BLR, function pointer tables and runtime buffer readers still need dataflow analysis.",
            "No 87,445 numeric OID candidates are upgraded by this survey.",
        ],
    }
    return report, hits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--writers", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args()
    report, hits = analyze(
        args.main.read_bytes(),
        json.loads(args.writers.read_text(encoding="utf-8")),
    )
    args.dest.mkdir(parents=True, exist_ok=True)
    (args.dest / "exefs_descriptor_entry_xrefs.json").write_text(
        json.dumps({"report": report, "xrefs": hits}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (args.dest / "exefs_descriptor_entry_xrefs.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLS)
        writer.writeheader()
        for row in hits:
            copy = dict(row)
            copy["instruction_words"] = json.dumps(row["instruction_words"])
            writer.writerow(copy)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
