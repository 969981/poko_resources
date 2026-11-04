"""Combine M3 per-container prefix scans, detect duplicates/coverage gaps."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from .core import save_csv, save_json

EXPECTED_KT = 79714
EXPECTED_LINK_TOTAL = 12298
EXPECTED_EMPTY_LINK = 2505


def run(parts_dir: Path, dest: Path):
    files = sorted(Path(parts_dir).rglob("*.csv"))
    if not files:
        raise FileNotFoundError("M3_NO_PARTIAL_CSV")
    records = []
    seen = set()
    dupes = []
    for p in files:
        with p.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                key = row.get("record_id", "")
                if not key:
                    raise ValueError("M3_MISSING_RECORD_ID:" + str(p))
                if key in seen:
                    dupes.append(key)
                seen.add(key)
                records.append(row)
    status = Counter(row["status"] for row in records)
    signatures = Counter(row["signature"] for row in records)
    by_type = defaultdict(Counter)
    for row in records:
        if row["catalog"] != "link":
            by_type[row["type_hash"]][row["signature"]] += 1
    kt = sum(r["catalog"] != "link" for r in records)
    link = len(records) - kt
    empty_link = sum(r["catalog"] == "link" and r["status"] == "EMPTY_INDEX" for r in records)
    expected = EXPECTED_KT + EXPECTED_LINK_TOTAL
    anomalies = []
    if dupes:
        anomalies.append("DUPLICATE_RECORD_IDS")
    if kt != EXPECTED_KT:
        anomalies.append(f"KT_PROBE_COUNT_MISMATCH:{kt}:{EXPECTED_KT}")
    if link != EXPECTED_LINK_TOTAL:
        anomalies.append(f"LINK_PROBE_COUNT_MISMATCH:{link}:{EXPECTED_LINK_TOTAL}")
    if empty_link != EXPECTED_EMPTY_LINK:
        anomalies.append(f"LINK_EMPTY_COUNT_MISMATCH:{empty_link}:{EXPECTED_EMPTY_LINK}")
    if status.get("PROBE_FAILED"):
        anomalies.append(f"M3_PROBE_FAILURES:{status['PROBE_FAILED']}")
    summary = {
        "status": "PASS_BOUNDED_PREFIX_SCAN" if not anomalies else "INCOMPLETE_PREFIX_SCAN",
        "expected_records": expected, "actual_records": len(records),
        "kt_records": kt, "link_records": link, "link_empty_entries": empty_link,
        "unique_record_ids": len(seen), "part_files": len(files),
        "signatures": dict(signatures), "statuses": dict(status),
        "anomalies": anomalies, "duplicate_examples": dupes[:15],
        "validation_level": "M3 signature survey only, NOT semantic parsing",
        "limitations": [
            "First <=96 decoded bytes are sampled per record; no full-payload M3 hash verification.",
            "Candidate extensions are recommendations, not reconstructed source filenames.",
            "Unknown binary formats remain undecoded; a PASS is only prefix scan coverage."
        ]
    }
    dest = Path(dest)
    save_csv(dest / "m3_signatures.csv", sorted(records, key=lambda r: (r["catalog"], int(r["record_index"]))))
    save_csv(dest / "m3_by_type_hash.csv", [
        {"type_hash": h, "signature": signature, "records": count}
        for h, by_signature in sorted(by_type.items())
        for signature, count in sorted(by_signature.items())
    ])
    save_csv(dest / "m3_unprobed.csv", [r for r in records if r["status"] == "PROBE_FAILED"])
    save_json(dest / "m3_signatures_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    if anomalies:
        raise RuntimeError("M3_COVERAGE_GATE_FAILED:" + ";".join(anomalies))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("UnPack/2.0.1/_reports"))
    a = parser.parse_args()
    run(a.parts_dir, a.output)


if __name__ == "__main__":
    main()
