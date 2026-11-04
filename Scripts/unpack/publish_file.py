"""Extract a standalone KT .file IDRK payload into a source-named RomFS directory.

The wrapper header is validated against root/system RDB before writing.
Raw, uncompressed bodies remain labelled RAW_VERIFIED. Large records split
into <=80 MiB pieces to satisfy GitHub's 100 MiB object-size limit.
"""
import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

from .core import FormatError, parse_rdb, parse_rdx, read_idrk, save_csv, save_json, sha256_file
from .publish import source_directory
from .publish_stream import PieceWriter, copy_decoded_stream

KT_ROOT = Path("romfs/motor_asset_re/KIDS_PLATFORM_OUNCE")


def find_records(base, wanted):
    found = []
    for catalog in ("root", "system"):
        rdx = parse_rdx((base / f"{catalog}.rdx").read_bytes())
        records, _ = parse_rdb((base / f"{catalog}.rdb").read_bytes(), catalog, rdx)
        for row in records:
            if row.footer_magic == 0x0c01 and row.name_hash == wanted:
                found.append((catalog, row))
    return found


def run(base, out, hash_text, source_sha=None, max_total_mib=1500):
    base = Path(base).resolve()
    out = Path(out).resolve()
    wanted = int(hash_text, 16)
    source = base / "data" / f"0x{wanted:08x}.file"
    if not source.is_file():
        raise FileNotFoundError(source)
    source_hash = source_sha or sha256_file(source)
    directory = source_directory(out, "ktrdb", source, base)
    records = find_records(base, wanted)
    manifest = []
    if not records:
        report = {"hash": hash_text, "status": "NO_MATCHING_RDB_RECORD", "outputs": 0}
        save_json(out / "_reports" / f"file_{hash_text}.json", report)
        return report
    for catalog, record in records:
        row = {"source_path": "2.0.1/" + (KT_ROOT / "data" / source.name).as_posix(),
               "source_sha256": source_hash,
               "record_id": f"{catalog}:{record.record_index}",
               "offset": 0, "stored_size": record.fdata_entry_size,
               "unpacked_size": record.uncompressed_size,
               "decoder_status": "", "decoder_error": "",
               "output_path": "", "output_bytes": "", "output_sha256": "",
               "publish_status": "", "part_count": 0}
        try:
            with source.open("rb") as fd:
                header, _ = read_idrk(fd, 0, source.stat().st_size)
                if (header.name_hash != record.name_hash or header.type_hash != record.type_hash
                        or header.entry_size != record.fdata_entry_size
                        or header.unpacked_size != record.uncompressed_size
                        or header.entry_size != source.stat().st_size):
                    raise FormatError("STANDALONE_RDB_IDRK_MISMATCH")
                if header.unpacked_size > max_total_mib * 1024**2:
                    raise FormatError("SKIPPED_BATCH_BUDGET")
                subdir = "raw" if header.packed_size == header.unpacked_size else "decoded"
                name = f"{catalog}_{record.record_index:06d}_{wanted:08x}.standalone_file.bin"
                directory.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix=".extract-", dir=directory) as tmp:
                    writer = PieceWriter(Path(tmp), name, header.unpacked_size)
                    try:
                        copy_decoded_stream(fd, header, writer)
                        digest = writer.finish()
                    finally:
                        if writer.current:
                            writer.current.close()
                            writer.current = None
                    paths = []
                    for piece in writer.files:
                        dest = directory / subdir / piece.name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(piece, dest)
                        paths.append(dest.relative_to(out).as_posix())
                row.update(decoder_status="RAW_VERIFIED" if subdir == "raw" else "DECOMPRESSED",
                           publish_status="PUBLISHED",
                           output_path=";".join(paths), output_sha256=digest,
                           output_bytes=header.unpacked_size, part_count=len(paths))
        except (FormatError, OSError, ValueError) as exc:
            row["publish_status"] = "SKIPPED_BATCH_BUDGET" if str(exc) == "SKIPPED_BATCH_BUDGET" else "EXTRACTION_FAILED"
            row["decoder_error"] = str(exc)
        manifest.append(row)
    save_csv(directory / "_manifest.csv", manifest)
    report = {"hash": hash_text, "records": len(records),
              "published": sum(x["publish_status"] == "PUBLISHED" for x in manifest),
              "bytes": sum(int(x["output_bytes"]) for x in manifest if x["output_bytes"]),
              "statuses": {state: sum(x["publish_status"] == state for x in manifest)
                           for state in sorted(set(x["publish_status"] for x in manifest))}}
    save_json(out / "_reports" / f"file_{hash_text}.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, default=Path("2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE"))
    p.add_argument("--output", type=Path, default=Path("UnPack/2.0.1"))
    p.add_argument("--hash", required=True)
    p.add_argument("--source-sha")
    p.add_argument("--max-total-mib", type=int, default=1500)
    a = p.parse_args()
    run(a.base, a.output, a.hash.lower().removeprefix("0x"), a.source_sha, a.max_total_mib)


if __name__ == "__main__":
    main()
