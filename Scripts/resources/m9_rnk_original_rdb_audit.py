#!/usr/bin/env python3
"""M9.6: audit companion RNK hashes against the ORIGINAL root/system RDB/RDX.

An RDB hit is only a resource index entry. _RNK0000 bytes and IRNK names
remain unverified until a matching IDRK payload is acquired and parsed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path

from Scripts.unpack.core import parse_rdb, parse_rdx

ROOT = Path("2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE")
COLS = (
    "expected_rnk_hash", "catalog", "record_id", "rdb_byte_offset",
    "type_hash", "flags", "footer_layout", "footer_magic",
    "fdata_index", "fdata_offset", "fdata_entry_size", "uncompressed_size",
    "candidate_source_paths", "physical_input_status", "evidence_grade",
    "rnk_magic_verified", "native_irnk_parsed", "script_text_fk_verified",
)


def expected_hashes(report: dict) -> set[str]:
    values = report.get("source_name_hashes", {}).values()
    hashes = {str(x).lower().removeprefix("0x").zfill(8) for x in values}
    if not hashes or any(len(x) != 8 or any(c not in "0123456789abcdef" for c in x) for x in hashes):
        raise ValueError("Invalid or missing M9.3 RNK hashes")
    return hashes


def source_candidates(entry, rdx, prefix: Path) -> list[str]:
    if entry.footer_layout not in ("standard_13", "extended_17"):
        return []
    if entry.footer_magic == 0x0c01:
        return [(prefix / "data" / f"0x{entry.name_hash:08x}.file").as_posix()]
    if entry.footer_magic != 0x0401 or not (0 <= entry.fdata_index < len(rdx)):
        return []
    filename = rdx[entry.fdata_index].filename
    roots = [prefix, prefix / "MountPoint_1", prefix / "MountPoint_2"]
    flag = rdx[entry.fdata_index].platform_flags
    preferred = {0xffff: 0, 0xff01: 1, 0xff02: 2}.get(flag)
    if preferred is not None:
        roots = [roots[preferred]] + [x for i, x in enumerate(roots) if i != preferred]
    return [(x / filename).as_posix() for x in roots]


def input_status(paths: list[str], tracked: set[str]) -> str:
    if any(p in tracked for p in paths):
        return "RAW_CONTAINER_TRACKED_UNREAD"
    if any(p + ".7z.001" in tracked for p in paths):
        return "SPLIT_7Z_TRACKED_UNREAD"
    return "NO_PHYSICAL_CONTAINER_IN_GIT_TREE" if paths else "UNSUPPORTED_RDB_FOOTER"


def inventory(catalogs: dict, expected: set[str], tracked: set[str], prefix: Path):
    """catalogs maps name -> (RDB entries, RDX entries, original checksums)."""
    rows = []
    totals = {}
    for catalog, (entries, rdx, fingerprints) in sorted(catalogs.items()):
        totals[catalog] = {"records": len(entries), **fingerprints}
        for entry in entries:
            key = f"{entry.name_hash:08x}"
            if key not in expected:
                continue
            paths = source_candidates(entry, rdx, prefix)
            rows.append(dict(
                expected_rnk_hash=key, catalog=catalog,
                record_id=f"{catalog}:{entry.record_index}",
                rdb_byte_offset=entry.rdb_offset,
                type_hash=f"{entry.type_hash:08x}", flags=f"{entry.flags:08x}",
                footer_layout=entry.footer_layout,
                footer_magic=f"0x{entry.footer_magic:04x}",
                fdata_index=entry.fdata_index,
                fdata_offset=entry.fdata_offset,
                fdata_entry_size=entry.fdata_entry_size,
                uncompressed_size=entry.uncompressed_size,
                candidate_source_paths=paths,
                physical_input_status=input_status(paths, tracked),
                evidence_grade="ORIGINAL_RDB_INDEX_HASH_MATCH_ONLY",
                rnk_magic_verified=False,
                native_irnk_parsed=False,
                script_text_fk_verified=False,
            ))
    rows.sort(key=lambda r: (r["expected_rnk_hash"], r["catalog"], r["rdb_byte_offset"]))
    return rows, totals


def load_catalogs(prefix: Path):
    catalogs = {}
    for name in ("root", "system"):
        rdb = (prefix / f"{name}.rdb").read_bytes()
        rdx = (prefix / f"{name}.rdx").read_bytes()
        idx = parse_rdx(rdx)
        entries, meta = parse_rdb(rdb, name, idx)
        catalogs[name] = (entries, idx, {
            "rdb_sha256": hashlib.sha256(rdb).hexdigest(),
            "rdx_sha256": hashlib.sha256(rdx).hexdigest(),
            "advertised_records": meta["advertised"],
            "rdx_entries": len(idx),
        })
    return catalogs


def git_tree_paths(prefix: Path) -> set[str]:
    value = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "HEAD", "--", prefix.as_posix()],
        text=True, encoding="utf-8",
    )
    return set(value.splitlines())


def write_results(dest: Path, expected: set[str], rows: list[dict],
                  totals: dict, indexed_m3: int):
    dest.mkdir(parents=True, exist_ok=True)
    with (dest / "rnk_original_rdb_matches.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLS)
        writer.writeheader()
        for row in rows:
            item = dict(row)
            item["candidate_source_paths"] = json.dumps(row["candidate_source_paths"], ensure_ascii=False)
            writer.writerow(item)
    count = Counter(x["expected_rnk_hash"] for x in rows)
    result = {
        "status": "M9_ORIGINAL_RDB_RESOURCE_HASH_AUDIT_ONLY",
        "original_catalogs": totals,
        "m3_index_records_rechecked": indexed_m3,
        "per_hash": [
            {
                "expected_rnk_hash": key,
                "original_rdb_index_hits": count[key],
                "rdb_record_ids": [r["record_id"] for r in rows if r["expected_rnk_hash"] == key],
                "result": "ORIGINAL_RDB_INDEX_HIT_PAYLOAD_UNVERIFIED" if count[key]
                          else "NO_HASH_ENTRY_IN_SUPPLIED_ORIGINAL_RDB",
            }
            for key in sorted(expected)
        ],
        "rnk_payloads_verified": 0,
        "irnk_strings_recovered": 0,
        "new_script_scene_quest_building_text_foreign_keys": 0,
        "previous_numeric_oid_candidates_preserved_unverified": 87445,
        "limitations": [
            "This audit checks original root.rdb and system.rdb indices, not unindexed resource bundles.",
            "An absent RDB index entry does not establish that no matching file exists anywhere in the game.",
            "Presence of a hash in an RDB is NOT proof of _RNK0000 magic or of any semantic property name.",
            "The git tree check records availability; split archives are not reconstructed or validated here.",
            "No script/ExeFS consumer dataflow or M7 text foreign key is inferred from resource hashes.",
        ],
    }
    (dest / "rnk_original_rdb_audit.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, default=ROOT)
    parser.add_argument("--rnk-report", type=Path, required=True)
    parser.add_argument("--m3-index", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args()
    previous = json.loads(args.rnk_report.read_text(encoding="utf-8"))
    expected = expected_hashes(previous)
    if previous.get("numeric_oid_candidates_still_unverified") != 87445:
        raise ValueError("M9 numeric evidence baseline changed; review before running")
    with args.m3_index.open(encoding="utf-8-sig", newline="") as f:
        m3_count = sum(1 for _ in csv.DictReader(f))
    if m3_count != previous["m3_index_records_inspected"]:
        raise ValueError("M3 index coverage has changed; do not silently reuse old conclusions")
    catalogs = load_catalogs(args.raw_root)
    rows, totals = inventory(catalogs, expected, git_tree_paths(args.raw_root), args.raw_root)
    result = write_results(args.dest, expected, rows, totals, m3_count)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
