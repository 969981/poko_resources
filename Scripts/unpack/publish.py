"""Store Pokopia decoded records under source-mirrored RomFS directories.

Archive part suffixes (.7z.001, .7z.002) are removed by restoring first.
Do not publish a reconstructed source container, only per-record output.
"""
import argparse
import csv
import json
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path

from .core import save_csv, save_json, sha256_file
from .ktrdb import run as run_kt
from .linkdata import run as run_link

KT_REL = Path("romfs/motor_asset_re/KIDS_PLATFORM_OUNCE")


def source_directory(out, kind, source, kt_base=None):
    """Complete restored filename is the immediate directory containing its records."""
    out, source = Path(out), Path(source)
    if kind == "linkdata":
        if source.name != "LD_C0_R.BIN":
            raise ValueError("Unexpected LINKDATA source: " + str(source))
        return out / "romfs" / source.name
    if kind != "ktrdb" or kt_base is None:
        raise ValueError("KT base is required")
    rel = source.resolve().relative_to(Path(kt_base).resolve())
    if rel.suffix.lower() not in (".fdata", ".file"):
        raise ValueError("Unsupported KT source: " + str(rel))
    return out / KT_REL / rel


def publish_rows(rows, kind, scratch, out, bin_file=None, kt_base=None,
                 max_file=90 * 1024**2, max_total=600 * 1024**2):
    scratch, out = Path(scratch), Path(out).resolve()
    manifests = defaultdict(list)
    hashes = {}
    counts = defaultdict(int)
    accepted_bytes = 0
    for row in rows:
        state = row["status"]
        if state in ("DECOMPRESSED", "EMPTY_DECODED"):
            subdir = "decoded"
        elif state in ("RAW_VERIFIED", "DECODE_FAILED", "EXTRACTED"):
            subdir = "raw"
        else:
            continue
        if kind == "linkdata":
            if bin_file is None:
                raise ValueError("--bin required")
            src = Path(bin_file)
            name = f'{int(row["index"]):05d}.bin'
            source_rel = Path("romfs") / src.name
            record_id = row["index"]
            offset = row["offset"]
            stored_size = row["stored_size"]
        else:
            if not row.get("source_path"):
                continue
            src = Path(row["source_path"])
            source_rel = KT_REL / src.resolve().relative_to(Path(kt_base).resolve())
            mode = "standalone_file" if src.suffix.lower() == ".file" else "fdata_idrk"
            name = f'{row["catalog"]}_{int(row["record_index"]):06d}_{row["name_hash"]}.{mode}.bin'
            record_id = row["catalog"] + ":" + row["record_index"]
            offset = row["fdata_offset"]
            stored_size = row["fdata_entry_size"]

        folder = source_directory(out, kind, src, kt_base)
        dest = folder / subdir / name
        data_file = scratch / subdir / name
        record = {"source_path": "2.0.1/" + source_rel.as_posix(),
                  "source_sha256": "", "record_id": record_id, "offset": offset,
                  "stored_size": stored_size,
                  "unpacked_size": row.get("unpacked_size") or row.get("uncompressed_size", ""),
                  "decoder_status": state, "decoder_error": row.get("error", ""),
                  "output_path": dest.relative_to(out).as_posix(),
                  "output_bytes": "", "output_sha256": "", "publish_status": ""}
        if not data_file.is_file():
            record["publish_status"] = "PAYLOAD_NOT_GENERATED"
        else:
            size = data_file.stat().st_size
            record["output_bytes"] = size
            if size > max_file:
                record["publish_status"] = "SKIPPED_GITHUB_FILE_LIMIT"
            elif accepted_bytes + size > max_total:
                record["publish_status"] = "SKIPPED_BATCH_BUDGET"
            else:
                digest = sha256_file(data_file)
                key = str(src.resolve())
                if key not in hashes:
                    hashes[key] = sha256_file(src)
                record["source_sha256"] = hashes[key]
                record["output_sha256"] = digest
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.is_file() and dest.stat().st_size == size and sha256_file(dest) == digest:
                    record["publish_status"] = "ALREADY_PRESENT_VERIFIED"
                else:
                    shutil.copy2(data_file, dest)
                    if sha256_file(dest) != digest:
                        raise IOError("Hash mismatch: " + str(dest))
                    record["publish_status"] = "PUBLISHED"
                accepted_bytes += size
        counts[record["publish_status"]] += 1
        manifests[folder].append(record)
    for folder, records in manifests.items():
        save_csv(folder / "_manifest.csv", records)
    return {"kind": kind, "source_directories": len(manifests),
            "accepted_bytes": accepted_bytes, "publish_statuses": dict(counts)}


def run(args):
    if args.kind == "linkdata" and args.bin is None:
        raise ValueError("--bin is required")
    if args.kind == "ktrdb" and not args.only_fdata:
        raise ValueError("--only-fdata is required for safe batching")
    with tempfile.TemporaryDirectory(prefix="pokopia-publish-") as tmp:
        scratch = Path(tmp)
        if args.kind == "linkdata":
            unpack = run_link(args.idx, args.bin, scratch, args.start, args.limit,
                              dry_run=False, decode=True, resume=False, verify_only=False)
            csv_path = scratch / "linkdata_entries.csv"
        else:
            selected = {x.lower().removeprefix("0x") for x in args.only_fdata}
            unpack = run_kt(args.kt_base, scratch, extract=True, decode=True,
                            limit=args.limit, dry_run=False, resume=False,
                            verify_only=False, only_fdata=selected)
            csv_path = scratch / "rdb_records.csv"
        with csv_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        result = publish_rows(
            rows, args.kind, scratch, args.output, args.bin, args.kt_base,
            max_file=args.max_file_mib * 1024**2,
            max_total=args.max_total_mib * 1024**2)
    result["extractor_statuses"] = unpack["statuses"]
    key = "linkdata" if args.kind == "linkdata" else "ktrdb_" + "_".join(sorted(selected))
    save_json(args.output / "_reports" / (key + ".json"), result)
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", required=True, choices=("linkdata", "ktrdb"))
    p.add_argument("--output", type=Path, default=Path("UnPack/2.0.1"))
    p.add_argument("--idx", type=Path, default=Path("2.0.1/romfs/LI_C0_R.IDX"))
    p.add_argument("--bin", type=Path)
    p.add_argument("--kt-base", type=Path, default=Path("2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE"))
    p.add_argument("--only-fdata", action="append", default=[])
    p.add_argument("--start", type=int, default=0)
    p.add_argument("--limit", type=int)
    p.add_argument("--max-file-mib", type=int, default=90)
    p.add_argument("--max-total-mib", type=int, default=600)
    run(p.parse_args())


if __name__ == "__main__":
    main()
