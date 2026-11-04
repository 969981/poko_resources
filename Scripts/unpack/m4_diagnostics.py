"""Inspect only real M4 unresolved KIDSOBJDB records, without guessing semantics.

For the four fixed-field parser exceptions and RDOK-only records, read their
original decoded payload, verify M3 manifest SHA-256 and report bounded
header/word layouts. This diagnoses actual Pokopia structures and leaves all
unparsed game assets untouched.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from .core import FormatError, save_json
from .m4_batch import ROOT, safe_parts

MAX_BYTES = 4 * 1024 * 1024


def index_rows(index: Path) -> dict[str, dict]:
    with Path(index).open(encoding="utf-8-sig", newline="") as f:
        return {row["record_id"]: row for row in csv.DictReader(f)}


def requested_ids(unresolved: Path) -> set[str]:
    with Path(unresolved).open(encoding="utf-8-sig", newline="") as f:
        return {row["record_id"] for row in csv.DictReader(f)}


def selected_rows(index: Path, unresolved: Path) -> list[dict]:
    records = index_rows(index)
    wanted = requested_ids(unresolved)
    unknown = wanted - set(records)
    if unknown:
        raise ValueError("UNKNOWN_M4_DIAGNOSTIC_IDS:" + ",".join(sorted(unknown)))
    return [records[key] for key in sorted(wanted)]


def plan(index: Path, unresolved: Path, output: Path):
    paths = set()
    for record in selected_rows(index, unresolved):
        for path in safe_parts(ROOT, record):
            paths.add((ROOT / path.relative_to(ROOT.resolve())).as_posix())
    lines = ["/Scripts/"] + ["/" + item for item in sorted(paths)]
    Path(output).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"selected": len(selected_rows(index, unresolved)), "files": len(paths)}


def bounded_blocks(blob: bytes):
    if len(blob) < 28 or blob[:8] != b"_DOK0000":
        raise FormatError("INVALID_DOK")
    header_size, platform, entry_count, name_hash, declared = struct.unpack_from("<5I", blob, 8)
    if not 28 <= header_size <= len(blob):
        raise FormatError("INVALID_DOK_HEADER_SIZE")
    offset = (header_size + 3) & ~3
    if entry_count > 100_000:
        raise FormatError("DIAGNOSTIC_ENTRY_LIMIT")
    blocks = []
    for i in range(entry_count):
        if offset + 12 > len(blob):
            raise FormatError("DIAGNOSTIC_TRUNCATED_BLOCK")
        magic, length = blob[offset:offset + 8], struct.unpack_from("<I", blob, offset + 8)[0]
        if length < 12 or offset + length > len(blob):
            raise FormatError("DIAGNOSTIC_BAD_BLOCK_BOUNDS")
        data = blob[offset + 12: offset + length]
        words = [int.from_bytes(data[j:j+4], "little") for j in range(0, min(128, len(data) - len(data) % 4), 4)]
        record = {
            "index": i, "kind": magic.decode("ascii", "replace"),
            "offset": offset, "size": length, "payload_size": len(data),
            "words_u32_hex": [f"{word:08x}" for word in words],
            "head_64_hex": blob[offset: min(offset + 64, offset + length)].hex(),
        }
        if magic == b"IDOK0000" and length >= 24:
            name, typ, count = struct.unpack_from("<3I", blob, offset + 12)
            record.update(property_name_hash=f"{name:08x}", property_type_hash=f"{typ:08x}",
                          property_count=count)
            if count and length >= 36:
                first_type, first_count, first_name = struct.unpack_from("<3I", blob, offset + 24)
                record.update(first_property_type=first_type, first_property_count=first_count,
                              first_property_name_hash=f"{first_name:08x}")
        blocks.append(record)
        offset = (offset + length + 3) & ~3
    return {
        "header": {"size": header_size, "platform": platform, "entries": entry_count,
                   "name_hash": f"{name_hash:08x}", "declared_bytes": declared},
        "blocks": blocks, "end_offset": offset,
        "final_length": len(blob)
    }


def scan(index: Path, unresolved: Path, destination: Path):
    records = selected_rows(index, unresolved)
    results = []
    for row in records:
        rid = row["record_id"]
        info = {"record_id": rid, "source_path": row["source_path"],
                "output_path": row["output_path"], "expected_sha256": row["output_sha256"]}
        try:
            parts = safe_parts(ROOT, row)
            if sum(p.stat().st_size for p in parts) > MAX_BYTES:
                raise FormatError("M4_DIAGNOSTIC_TOO_BIG")
            blob = b"".join(p.read_bytes() for p in parts)
            digest = hashlib.sha256(blob).hexdigest()
            if digest != row["output_sha256"].lower():
                raise FormatError("DIAGNOSTIC_SHA256_MISMATCH")
            info.update(status="VERIFIED", bytes=len(blob), sha256=digest, **bounded_blocks(blob))
        except (ValueError, OSError) as exc:
            info.update(status="FAILED", error=str(exc))
        results.append(info)
    status = Counter(item["status"] for item in results)
    summary = {"selected_records": len(records), "status": dict(status), "results": results,
               "interpretation": "All U32 words are raw evidence, not assigned semantic meaning"}
    save_json(destination, summary)
    print(json.dumps({"selected": len(records), "status": dict(status)}), flush=True)
    if status["FAILED"]:
        raise RuntimeError("M4_DIAGNOSTIC_FAILED")
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", required=True, choices=("plan", "scan"))
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--unresolved", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    report = plan(a.index, a.unresolved, a.output) if a.mode == "plan" else scan(a.index, a.unresolved, a.output)
    print(json.dumps(report if a.mode == "plan" else report["status"]))


if __name__ == "__main__":
    main()
