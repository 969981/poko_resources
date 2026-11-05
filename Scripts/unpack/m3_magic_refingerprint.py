"""Reclassify already-validated M3 first-64-byte evidence with actual KT magic.

No 18GB game-blob download: GT1G, _A2G, _S2G and XF1G are identified from
the already-committed native bytes. G1T also occurs in 55 LINKDATA records
with no RDB type hash. Independent type-hash evidence is required before
grading anything MAGIC_AND_TKID.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from .core import save_csv, save_json
from .m3_types import KT_TYPES

ROOT = Path("UnPack/2.0.1/_reports")
MAGICS = {
    b"GT1G": ("G1T_TEXTURE_CONTAINER", "g1t"),
    b"_A2G": ("G1A_ANIMATION_CONTAINER", "g1a"),
    b"_S2G": ("G1S_NATIVE_CONTAINER", "g1s"),
    b"XF1G": ("G1E_EFFECT_CONTAINER", "g1e"),
}
EXPECTED_SIGNED = 92012
EXPECTED_TYPED = 89507


def read_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fingerprint(row):
    h = row.get("head_64_hex") or ""
    if not h:
        return None
    head = bytes.fromhex(h[:128])
    for magic, meaning in MAGICS.items():
        if head.startswith(magic):
            return meaning
    return None


def refresh(signatures, typed_rows, original_signatures_summary,
            original_type_summary):
    if len(signatures) != EXPECTED_SIGNED or len(typed_rows) != EXPECTED_TYPED:
        raise ValueError(f"M3_INPUT_COVERAGE_MISMATCH:{len(signatures)}:{len(typed_rows)}")
    ids = set()
    changes = Counter()
    hints = {}
    for row in signatures:
        rid = row["record_id"]
        if rid in ids:
            raise ValueError("DUPLICATE_M3_SIGNATURE_ID:" + rid)
        ids.add(rid)
        new = fingerprint(row)
        if new:
            sig, ext = new
            if row["signature"] != sig:
                row["signature"] = sig
                row["confidence"] = "HIGH"
                row["candidate_extension"] = "." + ext
                changes[sig] += 1
            hints[rid] = new
    grades = Counter()
    extensions = Counter()
    seen = set()
    conflicts = []
    for row in typed_rows:
        rid = row["record_id"]
        if rid in seen or rid not in ids:
            raise ValueError("INVALID_M3_TYPE_INDEX_ID:" + rid)
        seen.add(rid)
        if rid in hints:
            sig, native = hints[rid]
            linked_type = KT_TYPES.get((row.get("type_hash") or "").lower())
            if rid.startswith("link:"):
                if linked_type:
                    raise ValueError("LINKDATA_UNEXPECTED_RDB_TYPE_HASH")
                row["native_extension_hint"] = "." + native
                row["evidence_grade"] = "MAGIC_CONFIRMED"
                row["type_hash_hint"] = ""
            elif linked_type == native:
                row["native_extension_hint"] = "." + native
                row["evidence_grade"] = "MAGIC_AND_TKID"
                row["type_hash_hint"] = native
            else:
                conflicts.append({
                    "record_id": rid, "magic": native,
                    "type_hash": row.get("type_hash", ""), "type_hint": linked_type or ""})
                row["native_extension_hint"] = ""
                row["evidence_grade"] = "HASH_MAGIC_CONFLICT"
            row["magic_hint"] = native
            row["signature"] = sig
        grades[row["evidence_grade"]] += 1
        extensions[row.get("native_extension_hint") or "<unknown>"] += 1
    if conflicts:
        raise ValueError(f"M3_NATIVE_MAGIC_HASH_CONFLICT:{len(conflicts)}:{conflicts[:10]}")
    if len(seen) != EXPECTED_TYPED:
        raise ValueError("M3_TYPED_ID_COUNT_MISMATCH")
    ss = dict(original_signatures_summary)
    ss["signatures"] = dict(Counter(r["signature"] for r in signatures))
    ss["status"] = "PASS_VERIFIED_PREFIX_RECLASSIFICATION"
    ss["reclassified_native_magic_count"] = sum(changes.values())
    ss["refingerprint_source"] = "Previously extracted first 64 bytes, originally scanned in Actions 41847881448"
    ss["validation_level"] = "M3 native Magic + RDB type crosscheck; NOT full semantic conversion"
    ts = dict(original_type_summary)
    ts["status_counts"] = dict(grades)
    ts["extension_hint_counts"] = dict(extensions)
    ts["unknown_or_conflicted_records"] = grades.get("UNKNOWN_NATIVE_FORMAT", 0)
    ts["magic_reclassified_count"] = sum(changes.values())
    ts["native_format_magic_source"] = "Published resource prefixes and matching RDB type hashes"
    ts["semantic_conversion_complete"] = False
    report = {
        "signature_records": len(signatures), "type_index_records": len(typed_rows),
        "new_magic_evidence_records": sum(changes.values()),
        "new_magic_counts": dict(changes),
        "type_evidence_counts": dict(grades),
        "linkdata_magic_confirmed_records": sum(
            r["record_id"].startswith("link:") and r["evidence_grade"] == "MAGIC_CONFIRMED"
            for r in typed_rows
        ),
        "signature_source": "m3_signatures.csv original HEAD-64 decoded bytes",
        "asset_bytes_redownloaded": 0,
        "errors": conflicts,
        "notes": [
            "KT type_hash and native byte magic must agree for MAGIC_AND_TKID grade",
            "55 LINKDATA GT1G records have real Magic but no native RDB type hash",
            "A native extension is not a conversion to DDS, glTF, PNG, etc.",
        ],
    }
    return ss, ts, report


def run(signature_input=ROOT / "m3_signatures.csv",
        type_input=ROOT / "m3_resource_type_index.csv",
        old_signature_summary=ROOT / "m3_signatures_summary.json",
        old_type_summary=ROOT / "m3_resource_type_index_summary.json",
        output=ROOT):
    signatures = read_csv(signature_input)
    types = read_csv(type_input)
    ss = json.loads(Path(old_signature_summary).read_text(encoding="utf-8"))
    ts = json.loads(Path(old_type_summary).read_text(encoding="utf-8"))
    new_ss, new_ts, report = refresh(signatures, types, ss, ts)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    save_csv(output / "m3_signatures.csv", signatures)
    save_csv(output / "m3_resource_type_index.csv", types)
    save_json(output / "m3_signatures_summary.json", new_ss)
    save_json(output / "m3_resource_type_index_summary.json", new_ts)
    save_json(output / "m3_magic_refingerprint.json", report)
    print(json.dumps(report, indent=2), flush=True)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--signature-input", required=True, type=Path)
    p.add_argument("--type-input", required=True, type=Path)
    p.add_argument("--signature-summary", required=True, type=Path)
    p.add_argument("--type-summary", required=True, type=Path)
    p.add_argument("--output", type=Path, default=ROOT)
    a = p.parse_args()
    run(a.signature_input, a.type_input, a.signature_summary, a.type_summary, a.output)


if __name__ == "__main__":
    main()
