"""Publish Git-blob-native extension aliases without recopying game binaries.

Every native/<id>_<hash>.<extension> entry references the SAME Git blob as
the already-audited decoded/ or raw/ source. Large multi-piece records get
.part0001 aliases in their manifest order. No game bytes are downloaded.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath

from .core import save_csv, save_json

ROOT = Path("UnPack/2.0.1")
EXPECTED_TYPED_RECORDS = 79714
EXPECTED_SOURCE_RECORDS = 89507
RECORD = re.compile(r"^(root|system):([0-9]+)$")
EXTENSION = re.compile(r"^\.[a-z0-9_]{1,32}$")


def git(*args, input=None, check=True):
    return subprocess.run(["git", *args], input=input, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=check)


def read_tree(prefix=ROOT / "romfs"):
    """Read tree path+blob IDs only; ls-tree -l may lazy-fetch blob bodies."""
    raw = git("ls-tree", "-r", "-z", "HEAD", "--", prefix.as_posix()).stdout
    blobs = {}
    for line in raw.split(b"\0"):
        if not line:
            continue
        metadata, path = line.split(b"\t", 1)
        mode, kind, sha = metadata.decode("ascii").split()
        if kind != "blob" or mode not in ("100644", "100755"):
            continue
        blobs[path.decode("utf-8")] = sha
    return blobs


def native_entries(type_index: Path, blobs: dict):
    records, missing, aliases = [], [], []
    count = Counter()
    targets = set()
    with Path(type_index).open(newline="", encoding="utf-8-sig") as f:
        index_rows = list(csv.DictReader(f))
    if len(index_rows) != EXPECTED_SOURCE_RECORDS:
        raise ValueError(f"UNEXPECTED_PUBLISHED_INDEX_ROWS:{len(index_rows)}")
    for row in index_rows:
        record_id = row["record_id"]
        m = RECORD.fullmatch(record_id)
        if not m:
            count["untyped_link_records"] += 1
            continue
        ext = row.get("native_extension_hint", "")
        if not EXTENSION.fullmatch(ext):
            raise ValueError(f"MISSING_OR_INVALID_NATIVE_EXT:{record_id}:{ext}")
        if row["evidence_grade"] not in ("MAGIC_AND_TKID", "MAGIC_CONFIRMED", "EXTERNAL_TKID_INFERRED"):
            raise ValueError(f"UNTRUSTED_NATIVE_TYPE_EVIDENCE:{record_id}")
        source = PurePosixPath(row["source_path"])
        if source.is_absolute() or ".." in source.parts or source.parts[:2] != ("2.0.1", "romfs"):
            raise ValueError(f"UNSAFE_SOURCE_PATH:{record_id}")
        source_directory = (ROOT / PurePosixPath(*source.parts[1:])).as_posix()
        name_hash = row.get("name_hash", "")
        if not re.fullmatch(r"[0-9a-fA-F]{8}", name_hash):
            raise ValueError(f"INVALID_NAME_HASH:{record_id}")
        stem = f"{m[1]}_{int(m[2]):06d}_{name_hash.lower()}{ext}"
        original = [p for p in row["output_path"].split(";") if p]
        if not original:
            raise ValueError(f"NO_MANIFEST_BLOBS:{record_id}")
        source_paths = []
        new_paths = []
        already = 0
        for i, part in enumerate(original, 1):
            pure = PurePosixPath(part)
            if pure.is_absolute() or ".." in pure.parts or pure.parts[0] != "romfs":
                raise ValueError(f"UNSAFE_OUTPUT_PATH:{record_id}")
            source_file = (ROOT / pure).as_posix()
            sha = blobs.get(source_file)
            if not sha:
                missing.append({"record_id": record_id, "file": source_file})
                continue
            filename = stem + (f".part{i:04d}" if len(original) > 1 else "")
            dest = f"{source_directory}/native/{filename}"
            if dest in targets:
                raise ValueError(f"DUPLICATE_NATIVE_FILENAME:{dest}")
            targets.add(dest)
            current = blobs.get(dest)
            if current and current != sha:
                raise ValueError(f"EXISTING_NATIVE_BLOB_MISMATCH:{dest}")
            source_paths.append(source_file)
            new_paths.append(dest)
            already += bool(current == sha)
            aliases.append((dest, sha, source_file, current == sha, record_id))
        records.append({
            "record_id": record_id, "source_path": row["source_path"],
            "source_output": row["output_path"],
            "native_output": ";".join(new_paths),
            "native_extension": ext,
            "extension_evidence": row["evidence_grade"],
            "original_decoded_sha256": row["output_sha256"],
            "native_git_parts": len(new_paths),
            "native_blob_refs_verified": len(source_paths) == len(original),
        })
        count["typed_records"] += 1
        count["native_part_paths"] += len(new_paths)
        count["already_aliased_parts"] += already
    if count["typed_records"] != EXPECTED_TYPED_RECORDS:
        raise ValueError(f"KT_COUNT_MISMATCH:{count['typed_records']}")
    if missing:
        raise ValueError(f"SOURCE_BLOB_NOT_IN_GIT_TREE:{len(missing)}:{missing[:5]}")
    return records, aliases, dict(count)


def publish(index: Path, output: Path, batch_parts: int = 2500, apply: bool = False):
    if batch_parts < 1 or batch_parts > 10000:
        raise ValueError("INVALID_BATCH_PARTS")
    blobs = read_tree()
    records, aliases, counts = native_entries(index, blobs)
    pending = [(dest, sha) for dest, sha, src, exists, rid in aliases if not exists]
    counts["new_blob_aliases"] = len(pending)
    counts["existing_blob_aliases"] = len(aliases) - len(pending)
    print(json.dumps({"planned": counts, "read_existing_binary_bytes": 0}, indent=2), flush=True)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if not apply:
        return {"dry_run": True, **counts}
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
    completed = 0
    for start in range(0, len(pending), batch_parts):
        segment = pending[start:start + batch_parts]
        staged = b"".join(f"100644 {sha}\t{path}\0".encode("utf-8") for path, sha in segment)
        git("update-index", "-z", "--index-info", input=staged)
        staged_count = len(segment)
        if git("diff", "--cached", "--quiet", check=False).returncode:
            git("commit", "-m", f"data(unpack): native hash-typed Git blob aliases {start}-{start + staged_count} [skip ci]")
            git("push", "origin", "HEAD:2.0.1_unpack")
        completed += staged_count
        print(json.dumps({"alias_objects_committed": completed,
                          "alias_objects_total": len(pending)}), flush=True)
    final_blobs = read_tree()
    mismatches = [{"dest": d, "expected": sha, "actual": final_blobs.get(d)}
                  for d, sha, src, exists, rid in aliases if final_blobs.get(d) != sha]
    if mismatches:
        raise RuntimeError(f"NATIVE_ALIAS_GIT_TREE_SHA_MISMATCH:{len(mismatches)}:{mismatches[:5]}")
    counts["validated_github_aliases"] = len(aliases)
    save_csv(output / "native_aliases.csv", records)
    save_json(output / "native_aliases_summary.json", {
        "source_of_truth": "published M3 type index + Git blob SHAs",
        "counts": counts,
        "alias_validation": "Each native path points to the identical Git blob SHA as its decoded/raw source",
        "storage_note": "Aliases are new Git tree references, not duplicated binary Git blobs",
        "sha256_note": "Original decoded SHA-256 from prior publisher; this step verifies Git blob identity without reading binary bytes",
        "semantic_note": "Native filename extensions inferred from KT type-hash unless Magic-confirmed; does not convert textures or meshes",
    })
    git("add", "--sparse", "-f", "--", str(output / "native_aliases.csv"),
        str(output / "native_aliases_summary.json"))
    if git("diff", "--cached", "--quiet", check=False).returncode:
        git("commit", "-m", "audit(unpack): verify native file aliases against source Git blob SHAs [skip ci]")
        git("push", "origin", "HEAD:2.0.1_unpack")
    return counts


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--type-index", type=Path, required=True)
    p.add_argument("--output", type=Path, default=ROOT / "_reports")
    p.add_argument("--batch-parts", type=int, default=2500)
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    publish(a.type_index, a.output, batch_parts=a.batch_parts, apply=a.apply)


if __name__ == "__main__":
    main()
