"""Merge M4 KIDSOBJDB shard evidence with exact published source-record coverage.

Compressed JSONL contains bounded, parsed IDOK data and opaque RDOK block
metadata. CSV index lets tools join original hash/path and parser status.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from collections import Counter
from pathlib import Path

from .core import save_csv, save_json
from .m4_batch import select_rows

EXPECTED = 4144


def run(parts_dir: Path, type_index: Path, output: Path, shards: int = 8, expected_total: int = EXPECTED):
    parts_dir, output = Path(parts_dir), Path(output)
    expected_by_shard = [{row["record_id"] for row in select_rows(type_index, part, shards)}
                         for part in range(shards)]
    all_expected = set().union(*expected_by_shard)
    if len(all_expected) != expected_total:
        raise ValueError(f"M4_SOURCE_INDEX_COUNT_MISMATCH:{len(all_expected)}:{expected_total}")
    seen = set()
    summaries = []
    all_rows = []
    statuses = Counter()
    blocks = Counter()
    anomalies = []
    for shard in range(shards):
        stem = f"m4_shard{shard:02d}"
        csv_file = parts_dir / (stem + ".csv")
        summary_file = parts_dir / (stem + ".summary.json")
        compressed_file = parts_dir / (stem + ".jsonl.gz")
        if not csv_file.is_file() or not summary_file.is_file() or not compressed_file.is_file():
            raise FileNotFoundError(f"M4_SHARD_FILES_MISSING:{shard}")
        summary = json.loads(summary_file.read_text(encoding="utf-8"))
        if summary["shard"] != shard or summary["shards"] != shards:
            raise ValueError(f"M4_WRONG_SHARD_METADATA:{shard}")
        with csv_file.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        actual = set()
        for row in rows:
            rid = row["record_id"]
            if rid in seen or rid in actual:
                anomalies.append("DUPLICATE_ID:" + rid)
            actual.add(rid)
            seen.add(rid)
            all_rows.append(row)
            statuses[row["status"]] += 1
            for key in ("idok_blocks", "rdok_blocks", "unsupported_field_types", "partial_blocks"):
                if row.get(key, "").isdigit():
                    blocks[key] += int(row[key])
        if actual != expected_by_shard[shard]:
            anomalies.append(
                f"SHARD_ID_MISMATCH:{shard}:missing={len(expected_by_shard[shard]-actual)}:"
                f"unexpected={len(actual-expected_by_shard[shard])}"
            )
        # Validate that each compressed, more detailed structural document has
        # the same per-record IDs and status as the accompanying compact CSV.
        from_gzip = {}
        with gzip.open(compressed_file, "rt", encoding="utf-8") as f:
            for line in f:
                item = json.loads(line)
                rid = item["record_id"]
                if rid in from_gzip:
                    anomalies.append("DUPLICATE_GZIP_RECORD:" + rid)
                from_gzip[rid] = item["status"]
        if from_gzip != {row["record_id"]: row["status"] for row in rows}:
            anomalies.append("GZIP_CSV_RECORD_MISMATCH:" + stem)
        if len(rows) != summary["selected_records"]:
            anomalies.append("SHARD_COUNT_MISMATCH:" + stem)
        summaries.append(summary)
    if seen != all_expected:
        anomalies.append(f"TOTAL_ID_COVERAGE_MISMATCH:{len(seen)}:{len(all_expected)}")
    if len(all_rows) != expected_total:
        anomalies.append(f"TOTAL_RECORD_COUNT_MISMATCH:{len(all_rows)}:{expected_total}")
    unresolved = [row for row in all_rows if row["status"] != "FIXED_WIDTH_ONLY" or row.get("warnings")]
    totals = {
        "expected_records": expected_total, "reported_records": len(all_rows),
        "shards": shards, "distinct_record_ids": len(seen),
        "statuses": dict(statuses), "blocks": dict(blocks),
        "unresolved_records": len(unresolved),
        "failed_parse_records": statuses["PARSE_FAILED"],
        "metadata_complete": not anomalies,
        "semantic_complete": False,
        "evidence_level": "Typed IDOK fixed-width values (first 8 per field); RDOK opaque",
        "anomalies": anomalies,
        "remaining_barriers": [
            "Unknown KIDSOBJDB property types and RDOK structures are not decoded",
            "Only first 8 field values retained per property, not every value",
            "Other original asset families require separate type-aware converters",
            "27 source FDATA/FILE containers are missing for 6,118 RDB entries",
        ]
    }
    output.mkdir(parents=True, exist_ok=True)
    save_csv(output / "m4_kidsobjdb_index.csv", sorted(all_rows, key=lambda r: r["record_id"]))
    save_csv(output / "m4_kidsobjdb_unresolved.csv", unresolved)
    save_json(output / "m4_kidsobjdb_summary.json", totals)
    print(json.dumps(totals, ensure_ascii=False, indent=2), flush=True)
    if anomalies:
        raise ValueError("M4_SHARD_COVERAGE_ANOMALIES:" + ";".join(anomalies[:8]))
    return totals


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--parts-dir", type=Path, required=True)
    p.add_argument("--type-index", type=Path, required=True)
    p.add_argument("--output", type=Path, default=Path("UnPack/2.0.1/_reports"))
    p.add_argument("--shards", type=int, default=8)
    a = p.parse_args()
    run(a.parts_dir, a.type_index, a.output, shards=a.shards)


if __name__ == "__main__":
    main()
