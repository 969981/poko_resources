"""Rebuild per-source manifests from every Git commit, without downloading binary blobs.

When resource partitions are committed separately, a sparse checkout might not
include earlier _manifest.csv versions. Merge the manifest history (oldest to
newest), then cross-check each published output path against the HEAD Git tree.
Requires actions/checkout with fetch-depth: 0.
"""
import argparse
import csv
import io
import json
import subprocess
from collections import Counter
from pathlib import Path

from .core import save_csv, save_json

PREFIX = "UnPack/2.0.1/romfs/"


def git(*args):
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8")


def run(output=Path("UnPack/2.0.1"), prefix=PREFIX):
    tree = {}
    for line in git("ls-tree", "-r", "-l", "HEAD", "--", str(output / "romfs")).splitlines():
        metadata, filename = line.split("\t", 1)
        fields = metadata.split()
        if fields[1] == "blob" and fields[3].isdigit():
            tree[filename] = int(fields[3])
    manifest_paths = sorted(p for p in tree if p.startswith(prefix) and p.endswith("/_manifest.csv"))
    totals = Counter()
    by_source = {}
    for manifest in manifest_paths:
        history = git("log", "--full-history", "--reverse", "--format=%H", "--", manifest).splitlines()
        merged = {}
        for commit in history:
            try:
                contents = git("show", commit + ":" + manifest)
            except subprocess.CalledProcessError:
                continue
            for row in csv.DictReader(io.StringIO(contents)):
                if not row.get("record_id"):
                    continue
                prior = merged.get(row["record_id"])
                if (prior and prior.get("publish_status") in ("PUBLISHED", "ALREADY_PRESENT_VERIFIED")
                        and row.get("publish_status") not in ("PUBLISHED", "ALREADY_PRESENT_VERIFIED")
                        and prior.get("source_sha256") == row.get("source_sha256")):
                    continue  # Do not erase a successful export with a later batch-budget skip.
                merged[row["record_id"]] = row
        verified = 0
        missing = 0
        known_outputs = set()
        for row in merged.values():
            if row.get("publish_status") not in ("PUBLISHED", "ALREADY_PRESENT_VERIFIED"):
                continue
            expected = [str(output / p) for p in row.get("output_path", "").split(";") if p]
            known_outputs.update(expected)
            expected_bytes = int(row.get("output_bytes") or -1)
            actual_bytes = sum(tree.get(p, 0) for p in expected)
            if expected and all(p in tree for p in expected) and actual_bytes == expected_bytes:
                verified += 1
            else:
                row["publish_status"] = "MISSING_ON_GIT"
                row["decoder_error"] = (row.get("decoder_error", "") + " Missing Git HEAD output").strip()
                missing += 1
        folder_prefix = manifest.removesuffix("_manifest.csv")
        actual = {p for p in tree if p.startswith(folder_prefix) and ("/decoded/" in p or "/raw/" in p)}
        extra = sorted(actual - known_outputs)
        by_source[manifest] = {"manifest_records": len(merged),
                               "published_verified": verified,
                               "missing_on_git": missing,
                               "unmanifested_output_files": len(extra),
                               "unmanifested_examples": extra[:10],
                               "history_versions": len(history)}
        totals["records"] += len(merged)
        totals["published_verified"] += verified
        totals["published_bytes"] += sum(int(row.get("output_bytes") or 0) for row in merged.values() if row.get("publish_status") in ("PUBLISHED", "ALREADY_PRESENT_VERIFIED"))
        totals["missing_on_git"] += missing
        totals["unmanifested_files"] += len(extra)
        save_csv(Path(manifest), [merged[k] for k in sorted(merged)])
    report = {"overall": dict(totals), "source_manifests": by_source}
    save_json(output / "_reports" / "manifest_reconciliation.json", report)
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2), flush=True)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, default=Path("UnPack/2.0.1"))
    args = p.parse_args()
    run(args.output)


if __name__ == "__main__":
    main()
