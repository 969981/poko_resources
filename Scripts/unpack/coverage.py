"""Inventory-backed, reproducible Pokopia 2.0.1 unpack coverage gate.

Uses Git tree names, parsed original IDX/RDB/RDX and reconciled published
manifests; never downloads whole decoded resource blobs. Missing platform
containers are reported as missing input, NOT as decompression failures.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from .core import parse_idx, parse_rdb, parse_rdx, save_csv, save_json

ROOT = "2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE"
OUT = Path("UnPack/2.0.1")
COMPLETE = {"PUBLISHED", "ALREADY_PRESENT_VERIFIED", "ALREADY_PRESENT_GIT_REFERENCE"}


def git(*args):
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8")


def git_bytes(path):
    return subprocess.check_output(["git", "show", f"HEAD:{path}"])


def published_ids(manifests, read=git_bytes):
    ids = set()
    invalid = []
    for path in manifests:
        for row in csv.DictReader(io.StringIO(read(path).decode("utf-8-sig"))):
            if row.get("publish_status") not in COMPLETE:
                continue
            key = row.get("record_id", "")
            if path.endswith("/LD_C0_R.BIN/_manifest.csv"):
                if key:
                    ids.add(("link", str(int(key))))
                else:
                    invalid.append((path, "EMPTY_LINK_ID"))
            elif ":" in key:
                ids.add(tuple(key.split(":", 1)))
            else:
                invalid.append((path, key))
    return ids, invalid


def available_filenames(names):
    result = set()
    for item in names:
        if not item.startswith(ROOT + "/"):
            continue
        if item.endswith(".fdata") or item.endswith(".file"):
            result.add(item.rsplit("/", 1)[-1])
        elif item.endswith(".7z.001"):
            result.add(item.rsplit("/", 1)[-1].removesuffix(".7z.001"))
    return result


def scan(names, read=git_bytes):
    names = set(names)
    manifests = sorted(p for p in names if p.startswith(str(OUT / "romfs") + "/")
                       and p.endswith("/_manifest.csv"))
    published, invalid = published_ids(manifests, read)
    if not manifests or invalid:
        raise ValueError(f"MANIFEST_NOT_RECONCILED: count={len(manifests)} invalid={invalid[:5]}")
    present = available_filenames(names)
    count = Counter()
    missing = defaultdict(lambda: {"records": 0, "unpacked_bytes": 0, "catalogs": set(), "platform_flags": set()})
    missing_rows = []
    unpublished_rows = []
    unexpected = []
    counted_ids = set()
    for catalog in ("root", "system"):
        rdx = parse_rdx(read(f"{ROOT}/{catalog}.rdx"))
        entries, metadata = parse_rdb(read(f"{ROOT}/{catalog}.rdb"), catalog, rdx)
        count[f"{catalog}_rdb_records"] = len(entries)
        count[f"{catalog}_rdx_entries"] = len(rdx)
        for r in entries:
            key = (catalog, str(r.record_index))
            if key in published:
                counted_ids.add(key)
                count["rdb_published"] += 1
                continue
            if r.footer_layout not in ("standard_13", "extended_17"):
                count["unsupported_footer_layout"] += 1
                unpublished_rows.append({"catalog": catalog, "record_index": r.record_index,
                                         "status": "UNSUPPORTED_FOOTER_LAYOUT", "name_hash": f"{r.name_hash:08x}"})
                continue
            if r.footer_magic == 0x0401:
                source = rdx[r.fdata_index].filename
                platform = f"{rdx[r.fdata_index].platform_flags:04x}"
            elif r.footer_magic == 0x0c01:
                source = f"0x{r.name_hash:08x}.file"
                platform = "STANDALONE"
            else:
                count["unsupported_footer_magic"] += 1
                unpublished_rows.append({"catalog": catalog, "record_index": r.record_index,
                                         "status": "UNSUPPORTED_FOOTER_MAGIC", "name_hash": f"{r.name_hash:08x}"})
                continue
            if source in present:
                count["source_present_unpublished"] += 1
                unpublished_rows.append({"catalog": catalog, "record_index": r.record_index,
                                         "status": "SOURCE_PRESENT_UNPUBLISHED",
                                         "source_file": source, "name_hash": f"{r.name_hash:08x}"})
            else:
                count["missing_source_records"] += 1
                m = missing[source]
                m["records"] += 1
                m["unpacked_bytes"] += r.uncompressed_size
                m["catalogs"].add(catalog)
                m["platform_flags"].add(platform)
                missing_rows.append({
                    "catalog": catalog, "record_index": r.record_index,
                    "record_id": f"{catalog}:{r.record_index}",
                    "source_file": source,
                    "name_hash": f"{r.name_hash:08x}",
                    "type_hash": f"{r.type_hash:08x}",
                    "unpacked_size": r.uncompressed_size,
                    "platform_flags": platform,
                    "reason": "PHYSICAL_INPUT_NOT_IN_2.0.1_ROMFS"
                })
    idx = parse_idx(read("2.0.1/romfs/LI_C0_R.IDX"))
    count["link_index_records"] = len(idx)
    for e in idx:
        key = ("link", str(e.index))
        if key in published:
            counted_ids.add(key)
            count["link_published"] += 1
        elif e.stored_size == 0:
            count["link_empty_index_entries"] += 1
        else:
            count["link_source_present_unpublished"] += 1
            unpublished_rows.append({"catalog": "link", "record_index": e.index,
                                     "status": "LINK_SOURCE_PRESENT_UNPUBLISHED",
                                     "source_file": "LD_C0_R.BIN"})
    for key in published - counted_ids:
        unexpected.append(":".join(key))
    count["unexpected_manifest_records"] = len(unexpected)
    count["published_manifest_records"] = len(published)
    audit_raw = json.loads(read(str(OUT / "_reports/manifest_reconciliation.json")))
    audited = audit_raw["overall"]
    if audited.get("missing_or_wrong_size", 0) or audited.get("unmanifested_output_files", 0):
        raise ValueError("GIT_TREE_AUDIT_HAS_ERRORS")
    if count["published_manifest_records"] != audited.get("published_verified_size"):
        raise ValueError("PUBLISHED_COUNT_MISMATCH_WITH_GIT_TREE_AUDIT")
    grouped = sorted(({"source_file": k, "rdb_records": v["records"],
                       "expected_unpacked_bytes": v["unpacked_bytes"],
                       "catalogs": ";".join(sorted(v["catalogs"])),
                       "platform_flags": ";".join(sorted(v["platform_flags"]))}
                      for k, v in missing.items()), key=lambda x: (-x["rdb_records"], x["source_file"]))
    report = {"overall": dict(count),
              "coverage": {
                  "rdb_published_of_total": [count["rdb_published"],
                                             count["root_rdb_records"] + count["system_rdb_records"]],
                  "link_published_and_empty_of_total": [
                      count["link_published"] + count["link_empty_index_entries"],
                      count["link_index_records"]
                  ],
                  "remaining_missing_physical_inputs": len(grouped),
              },
              "missing_sources": grouped,
              "unpublished_examples": unpublished_rows[:25],
              "unexpected_manifest_examples": sorted(unexpected)[:25],
              "limitations": [
                  "Git-tree validation checks path and blob byte size, not rehashing all SHA-256.",
                  "Record extraction is not semantic parsing of textures, models, databases or FlatBuffers.",
                  "Missing physical inputs cannot be reconstructed from RDX catalog entries."
              ]}
    return report, missing_rows, unpublished_rows


def run(output=OUT):
    output = Path(output)
    files = git("ls-tree", "-r", "--name-only", "HEAD", "--", "2.0.1/romfs", str(output / "romfs"),
                str(output / "_reports/manifest_reconciliation.json")).splitlines()
    report, missing, unpublished = scan(files)
    save_json(output / "_reports/source_coverage.json", report)
    save_csv(output / "_reports/missing_input_records.csv", missing)
    save_csv(output / "_reports/unpublished_records.csv", unpublished)
    print(json.dumps(report["coverage"], ensure_ascii=False, indent=2), flush=True)
    if report["overall"].get("source_present_unpublished", 0) or report["overall"].get("link_source_present_unpublished", 0):
        raise RuntimeError("SOURCE_PRESENT_BUT_UNPUBLISHED: see unpublished_records.csv")
    if report["overall"].get("unexpected_manifest_records", 0):
        raise RuntimeError("UNKNOWN_PUBLISHED_MANIFEST_IDS: see source_coverage.json")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
