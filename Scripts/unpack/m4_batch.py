"""M4 KIDSOBJDB batch parser over Git-sparse, hash-verified published assets.

Plan only selects precise paths for a deterministic Git sparse-checkout shard;
scan serializes typed IDOK numeric fields (bounded samples) and explicitly
marks opaque RDOK/unknown property types without inventing semantic values.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import math
import hashlib
import json
from collections import Counter
from pathlib import Path, PurePosixPath

from .decode_kidsobjdb import parse
from .core import save_json

ROOT = Path("UnPack/2.0.1")


def select_rows(index, shard, shards):
    if shards < 1 or not 0 <= shard < shards:
        raise ValueError("INVALID_M4_SHARD")
    with Path(index).open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if r.get("native_extension_hint") == ".kidsobjdb"
                and r.get("evidence_grade") in ("MAGIC_AND_TKID", "MAGIC_CONFIRMED")]
    selected = []
    for row in rows:
        rid = row["record_id"]
        if int.from_bytes(hashlib.sha256(rid.encode()).digest()[:4], "big") % shards == shard:
            selected.append(row)
    return sorted(selected, key=lambda r: r["record_id"])


def safe_parts(root, row):
    relative = [s for s in row.get("output_path", "").split(";") if s]
    if not relative:
        raise ValueError("MISSING_KIDSOBJDB_OUTPUT_PATH")
    base = Path(root).resolve()
    targets = []
    for p in relative:
        posix = PurePosixPath(p)
        if posix.is_absolute() or ".." in posix.parts or posix.parts[0] != "romfs":
            raise ValueError("KIDSOBJDB_UNSAFE_OUTPUT_PATH")
        item = base.joinpath(*posix.parts).resolve()
        if not item.is_relative_to(base):
            raise ValueError("KIDSOBJDB_ESCAPE_OUTPUT_ROOT")
        targets.append(item)
    return targets


def plan(index, shard, shards, patterns):
    rows = select_rows(index, shard, shards)
    sources = set()
    for row in rows:
        for p in safe_parts(ROOT, row):
            sources.add((ROOT / p.relative_to(ROOT.resolve())).as_posix())
    listing = ["/Scripts/", "/tests/"] + ["/" + s for s in sorted(sources)]
    Path(patterns).write_text("\n".join(listing) + "\n", encoding="utf-8")
    print(json.dumps({"shard": shard, "shards": shards, "selected_records": len(rows),
                      "specific_asset_files": len(sources)}), flush=True)
    return rows


def json_safe(item):
    if isinstance(item, float) and not math.isfinite(item):
        return "NaN" if math.isnan(item) else ("Infinity" if item > 0 else "-Infinity")
    if isinstance(item, list):
        return [json_safe(v) for v in item]
    if isinstance(item, dict):
        return {k: json_safe(v) for k, v in item.items()}
    return item


def inspect(index, shard, shards, output, max_record_mib=64, sampled_values=8):
    rows = select_rows(index, shard, shards)
    out = Path(output)
    if not out.name.endswith(".jsonl.gz"):
        raise ValueError("M4_OUTPUT_EXPECTS_COMPRESSED_JSONL")
    out.parent.mkdir(parents=True, exist_ok=True)
    stem = out.name.removesuffix(".jsonl.gz")
    statuses = Counter()
    concise = []
    with gzip.open(out, "wt", encoding="utf-8", compresslevel=6) as writer:
        for row in rows:
            rid = row["record_id"]
            result = {
                "record_id": rid, "source_path": row["source_path"],
                "name_hash": row["name_hash"], "type_hash": row["type_hash"],
                "output_path": row["output_path"],
                "expected_sha256": row["output_sha256"],
            }
            try:
                paths = safe_parts(ROOT, row)
                total_size = 0
                chunks = []
                for p in paths:
                    size = p.stat().st_size
                    total_size += size
                    if total_size > max_record_mib * 1024**2:
                        raise ValueError("KIDSOBJDB_RECORD_EXCEEDS_LIMIT")
                    chunks.append(p.read_bytes())
                blob = b"".join(chunks)
                sha = hashlib.sha256(blob).hexdigest()
                if sha != row["output_sha256"].lower():
                    raise ValueError("KIDSOBJDB_MANIFEST_SHA256_MISMATCH")
                parsed = parse(blob, max_sampled_values=sampled_values)
                result.update(status=parsed["semantic_status"], decoded=parsed)
                concise.append({
                    "record_id": rid, "source_path": row["source_path"],
                    "name_hash": row["name_hash"], "type_hash": row["type_hash"],
                    "sha256": sha, "bytes": len(blob),
                    "status": parsed["semantic_status"],
                    "idok_blocks": parsed["summary"]["IDOK"],
                    "rdok_blocks": parsed["summary"]["RDOK"],
                    "unsupported_field_types": parsed["summary"]["UNSUPPORTED_TYPES"],
                    "partial_blocks": parsed["summary"]["PARTIAL_BLOCKS"],
                    "warnings": ";".join(parsed["warnings"]),
                })
            except (OSError, ValueError) as error:
                result.update(status="PARSE_FAILED", error=str(error))
                concise.append({
                    "record_id": rid, "source_path": row["source_path"],
                    "name_hash": row["name_hash"], "type_hash": row["type_hash"],
                    "sha256": "", "bytes": "", "status": "PARSE_FAILED",
                    "idok_blocks": "", "rdok_blocks": "",
                    "unsupported_field_types": "", "partial_blocks": "",
                    "warnings": str(error),
                })
            statuses[result["status"]] += 1
            writer.write(json.dumps(json_safe(result), ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    csv_out = out.with_name(stem + ".csv")
    from .core import save_csv
    save_csv(csv_out, concise)
    summary = {"shard": shard, "shards": shards, "selected_records": len(rows),
               "statuses": dict(statuses), "output": str(out),
               "structured_records": str(csv_out),
               "scan_level": "M4 fixed-width IDOK; opaque RDOK retained; sampled values only"}
    save_json(out.with_name(stem + ".summary.json"), summary)
    print(json.dumps(summary), flush=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("plan", "scan"), required=True)
    p.add_argument("--index", type=Path, required=True)
    p.add_argument("--shard", type=int, required=True)
    p.add_argument("--shards", type=int, default=8)
    p.add_argument("--patterns", type=Path)
    p.add_argument("--output", type=Path)
    p.add_argument("--sampled-values", type=int, default=8)
    a = p.parse_args()
    if a.mode == "plan":
        if a.patterns is None:
            p.error("--patterns is required")
        plan(a.index, a.shard, a.shards, a.patterns)
    else:
        if a.output is None:
            p.error("--output is required")
        inspect(a.index, a.shard, a.shards, a.output, sampled_values=a.sampled_values)


if __name__ == "__main__":
    main()
