"""Reconstruct native-suffix files from verified Pokopia 2.0.1 Git blobs.

Source-mirrored decoded artifacts and manifests remain unchanged. Reads every
existing .partNNNN in manifest order, uses streaming SHA-256 to verify the
recombined payload, and atomically exports native files outside the Git tree.
Unknown and external-only extension guesses require explicit opt-in.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import tempfile
from pathlib import Path, PurePosixPath

from .core import save_csv

DEFAULT_ROOT = Path("UnPack/2.0.1")


def checked_source_path(root: Path, relative: str) -> Path:
    p = PurePosixPath(relative)
    if p.is_absolute() or ".." in p.parts or not p.parts or p.parts[0] != "romfs":
        raise ValueError("UNSAFE_MANIFEST_ASSET_PATH:" + relative)
    root = root.resolve()
    destination = root.joinpath(*p.parts).resolve()
    if not destination.is_relative_to(root):
        raise ValueError("ASSET_PATH_OUTSIDE_ROOT:" + relative)
    return destination


def native_destination(destination_root: Path, source: str, record_id: str, name_hash: str, suffix: str) -> Path:
    if not source.startswith("2.0.1/romfs/"):
        raise ValueError("UNRECOGNIZED_SOURCE_PATH:" + source)
    subfolder = source.removeprefix("2.0.1/")
    s = PurePosixPath(subfolder)
    if ".." in s.parts or s.is_absolute():
        raise ValueError("UNSAFE_NATIVE_DESTINATION")
    if not suffix.startswith(".") or not suffix[1:].replace("_", "").isalnum():
        raise ValueError("INVALID_NATIVE_SUFFIX")
    clean = record_id.replace(":", "_")
    if not all(c.isalnum() or c in "_-" for c in clean):
        raise ValueError("UNSAFE_NATIVE_RECORD_ID")
    hash_text = name_hash or "nohash"
    filename = f"{clean}_{hash_text}{suffix}"
    result = destination_root.resolve().joinpath(*s.parts, "native", filename).resolve()
    if not result.is_relative_to(destination_root.resolve()):
        raise ValueError("NATIVE_DESTINATION_ESCAPES_ROOT")
    return result


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export_record(root: Path, destination_root: Path, row: dict,
                  dry_run=False, max_mib=2048):
    source_paths = [s for s in row["output_path"].split(";") if s]
    if not source_paths:
        raise ValueError("MISSING_SOURCE_PARTS:" + row["record_id"])
    pieces = [checked_source_path(root, part) for part in source_paths]
    dest = native_destination(destination_root, row["source_path"],
                              row["record_id"], row["name_hash"], row["native_extension_hint"])
    sizes = []
    for item in pieces:
        if not item.is_file():
            if dry_run:
                return {"record_id": row["record_id"], "status": "MISSING_LOCAL_BLOB",
                        "destination": str(dest), "source_parts": len(pieces)}
            raise FileNotFoundError("MISSING_LOCAL_BLOB:" + str(item))
        sizes.append(item.stat().st_size)
    expected_size = sum(sizes)
    if expected_size > max_mib * 1024 * 1024:
        raise ValueError("OUTPUT_EXCEEDS_MAX_RECORD_SIZE:" + row["record_id"])
    expected_sha = row.get("output_sha256", "").lower()
    if len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha):
        raise ValueError("MISSING_SOURCE_SHA256:" + row["record_id"])
    result = {"record_id": row["record_id"], "status": "",
              "destination": str(dest), "bytes": expected_size,
              "sha256": expected_sha, "source_parts": len(pieces),
              "type_evidence": row["evidence_grade"]}
    if dry_run:
        result["status"] = "DRY_RUN"
        return result
    if dest.is_file():
        if dest.stat().st_size == expected_size and sha256(dest) == expected_sha:
            result["status"] = "ALREADY_VERIFIED"
            return result
        raise ValueError("EXISTING_DESTINATION_HASH_MISMATCH:" + str(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=dest.parent, prefix=".native-", delete=False) as tmp:
            temp_path = Path(tmp.name)
            digest = hashlib.sha256()
            actual = 0
            for part in pieces:
                with part.open("rb") as f:
                    for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
                        tmp.write(chunk)
                        digest.update(chunk)
                        actual += len(chunk)
            tmp.flush()
            os.fsync(tmp.fileno())
        if actual != expected_size or digest.hexdigest() != expected_sha:
            raise ValueError("REASSEMBLED_ASSET_SHA256_MISMATCH:" + row["record_id"])
        os.replace(temp_path, dest)
        temp_path = None
        result["status"] = "EXPORTED_HASH_VERIFIED"
        return result
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def run(index: Path, root: Path, destination_root: Path, extensions=None,
        record_id="", limit=None, allow_inferred=False, dry_run=False):
    records = []
    supported_grades = {"MAGIC_AND_TKID", "MAGIC_CONFIRMED"}
    if allow_inferred:
        supported_grades.add("EXTERNAL_TKID_INFERRED")
    wanted = set(x.removeprefix(".").lower() for x in extensions) if extensions else None
    with Path(index).open("r", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if record_id and row["record_id"] != record_id:
                continue
            ext = row.get("native_extension_hint", "").removeprefix(".").lower()
            if not ext or row.get("evidence_grade") not in supported_grades:
                continue
            if wanted is not None and ext not in wanted:
                continue
            records.append(row)
            if limit is not None and len(records) >= limit:
                break
    if record_id and not records:
        raise LookupError("REQUESTED_RECORD_NOT_ELIGIBLE_OR_NOT_FOUND:" + record_id)
    outcome = [export_record(Path(root), Path(destination_root), row, dry_run=dry_run)
               for row in records]
    save_csv(Path(destination_root) / "native_export_manifest.csv", outcome)
    return outcome


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--index", type=Path, default=DEFAULT_ROOT / "_reports/m3_resource_type_index.csv")
    p.add_argument("--assets-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--out", type=Path, required=True, help="Write native files OUTSIDE the Git checkout")
    p.add_argument("--extensions", default="", help="Comma-separated suffixes e.g. g1m,g1t,kidsobjdb")
    p.add_argument("--record-id", default="", help="Optional exact RDB ID, e.g. root:10349")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--allow-inferred", action="store_true", help="Permit unconfirmed external KT type mappings")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    if a.out.resolve().is_relative_to(Path(".").resolve() / "UnPack"):
        raise SystemExit("OUTPUT_MUST_BE_OUTSIDE_VERSIONED_UNPACK_DIR")
    results = run(a.index, a.assets_root, a.out, a.extensions.split(",") if a.extensions else None,
                  a.record_id, a.limit, a.allow_inferred, a.dry_run)
    print(f"Processed {len(results)} native records; verified={sum(r['status'] in ('EXPORTED_HASH_VERIFIED', 'ALREADY_VERIFIED') for r in results)}")


if __name__ == "__main__":
    main()
