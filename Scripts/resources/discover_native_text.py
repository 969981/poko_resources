#!/usr/bin/env python3
"""Inventory tagged text in already decoded Pokopia 2.0.1 LINKDATA entries.

Discovery only: text-like byte sequences are not automatically verified as
dialogue, language-specific strings, or the complete contents of the file.
Never rewrite game blobs. No third-party dependencies.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

NAME_RE = re.compile(r"^(\d{5})\.bin$")
CONTROL_RE = re.compile(r"<(?:\$[A-Za-z]|oneline>|clear>|br>)")
MIN_CHARS = 4
MAX_FILE_BYTES = 64 * 1024 * 1024

def segments(data: bytes):
    """Return byte-offset / decoded text pairs; retain source offsets."""
    start = 0
    for part in data.split(b"\x00"):
        offset = start
        start += len(part) + 1
        if len(part) < MIN_CHARS or len(part) > 16384:
            continue
        try:
            value = part.decode("utf-8", "strict")
        except UnicodeDecodeError:
            continue
        if len(value.strip()) < MIN_CHARS or not any(c.isalpha() for c in value):
            continue
        if sum(c.isprintable() or c in "\r\n\t" for c in value) / len(value) < .95:
            continue
        yield offset, value

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decoded-root", type=Path, required=True,
                    help="Directory containing 00000.bin ... (actual decoded LINKDATA entries)")
    ap.add_argument("--dest", type=Path, default=Path("UnPack/2.0.1/Resources/Localization"))
    ap.add_argument("--entries", type=int, nargs="*", default=None,
                    help="Optional entry IDs. By default scans all numbered *.bin files.")
    args = ap.parse_args()
    if not args.decoded_root.is_dir():
        ap.error(f"Decoded directory not found: {args.decoded_root}")
    args.dest.mkdir(parents=True, exist_ok=True)
    candidates = args.dest / "text_candidates.csv"
    file_index = args.dest / "source_files.csv"
    known = set(args.entries) if args.entries is not None else None
    files = [p for p in args.decoded_root.glob("*.bin")
             if NAME_RE.fullmatch(p.name) and
             (known is None or int(p.stem) in known)]
    rows, inventory = [], []
    for p in sorted(files, key=lambda v: int(v.stem)):
        size = p.stat().st_size
        if size > MAX_FILE_BYTES:
            inventory.append([int(p.stem), p.as_posix(), size, "", "SKIPPED_SIZE", 0])
            continue
        data = p.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        tagged = 0
        count = 0
        for offset, value in segments(data):
            # Only export tagged candidates. General UTF-8 strings often are
            # identifiers or unrelated metadata rather than localization.
            if not CONTROL_RE.search(value):
                continue
            rows.append([int(p.stem), p.as_posix(), digest, offset,
                         len(value.encode("utf-8")), value])
            tagged += 1
            count += 1
        inventory.append([int(p.stem), p.as_posix(), size, digest,
                          "TAGGED_CANDIDATE" if tagged else "NO_TAGGED_CANDIDATE", count])
    with candidates.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["entry_index", "source_path", "source_sha256",
                         "byte_offset", "text_utf8_byte_length", "raw_text_with_tags"])
        writer.writerows(rows)
    with file_index.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(["entry_index", "source_path", "source_size",
                         "source_sha256", "status", "tagged_candidate_count"])
        writer.writerows(inventory)
    report = {
        "input_root": args.decoded_root.as_posix(),
        "files_scanned": len(inventory),
        "tagged_candidates": len(rows),
        "localization_language": "UNKNOWN",
        "verification": "UNVERIFIED_CANDIDATE",
        "scope": "Null-terminated UTF-8 fragments with known dialogue control tags; not exhaustive",
        "warnings": [
            "A candidate may be a fragment, duplicate, or non-dialogue resource.",
            "These byte offsets address decoded files, not the compressed LINKDATA container.",
            "No language can be assigned from tags alone; correlate a real language selection or resource table.",
            "UTF-16, packed strings and strings without tags require separate parsers."
        ],
    }
    (args.dest / "discovery_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
