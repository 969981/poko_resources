#!/usr/bin/env python3
"""M5 KIDSOBJDB verification against original native bytes, not TSV joins alone."""
from __future__ import annotations
import argparse
import csv
import json
import struct
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=64)
def all_triples(path):
    blob = Path(path).read_bytes()
    # Verified layout: object hash @ p; G1T @ p+0x30; TEXINFO @ p+0x34.
    return {struct.unpack_from("<I", blob, i)[0:1] +
            struct.unpack_from("<II", blob, i + 0x30)
            for i in range(0, len(blob) - 55, 4)}


def name_pack(path):
    parent = path.parent.parent
    return parent.name.lower()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(
        "UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE"))
    p.add_argument("--resources", type=Path, default=Path("UnPack/2.0.1/Resources"))
    args = p.parse_args()
    src = args.resources / "Textures" / "Indexes"
    with (src / "layout-textures.tsv").open(encoding="utf-8-sig", newline="") as f:
        layout = list(csv.DictReader(f, delimiter="\t"))
    with (src / "item-texture-map.tsv").open(encoding="utf-8-sig", newline="") as f:
        mapping = list(csv.DictReader(f, delimiter="\t"))
    native = defaultdict(list)
    for file in args.root.rglob("*.kidsobjdb"):
        native[file.stem.rsplit("_", 1)[-1].lower()].append(file)
    counts, by_pair, unresolved = Counter(), defaultdict(list), Counter()
    results = []
    for r in layout:
        pack, name = r["objdb_file"].split("__", 1)
        key = name.removesuffix(".kidsobjdb")
        found = [file for file in native.get(key, ()) if name_pack(file) == pack.lower() + ".fdata"]
        if len(found) != 1:
            status = "MISSING_NATIVE_DB" if not found else "AMBIGUOUS_NATIVE_DB"
            path = ""
            unresolved[r["objdb_file"]] += 1
        else:
            path = found[0].as_posix()
            t = tuple(int(r[field], 16) for field in ("object_hash", "g1t_hash", "texinfo_hash"))
            status = "VERIFIED_FIELDS" if t in all_triples(path) else "FIELD_MISMATCH"
        out = dict(r, status=status, native_path=path)
        results.append(out)
        counts[status] += 1
        by_pair[(r["texinfo_hash"], r["g1t_hash"])].append(out)
    item_counts = Counter()
    for row in mapping:
        candidates = by_pair[(row["texinfo_hash"], row["g1t_hash"])]
        if len(candidates) == 1:
            item_counts[candidates[0]["status"]] += 1
        else:
            item_counts["AMBIGUOUS_OR_MISSING_PAIR"] += 1
    output = args.resources / "Textures"
    output.mkdir(parents=True, exist_ok=True)
    with (output / "layout_field_audit.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["texinfo_hash", "g1t_hash",
                                "object_hash", "objdb_file", "status", "native_path"])
        writer.writeheader()
        writer.writerows(results)
    summary = {
        "layout_rows": len(layout), "item_rows": len(mapping),
        "statuses": dict(counts), "mapped_item_statuses": dict(item_counts),
        "missing_native_databases": [
            {"name": name, "rows": n} for name, n in sorted(unresolved.items())],
        "field_offsets": {"object_hash": 0, "g1t_hash": 48, "texinfo_hash": 52},
        "note": "Native KIDSOBJDB hash triples are validated. PNG content, sprite UV crop and physical G1T existence are separate acceptance criteria."
    }
    (output / "layout_field_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assert len(results) == len(layout)
    assert item_counts["VERIFIED_FIELDS"] == len(mapping), "some item links lack native field proof"


if __name__ == "__main__":
    main()
