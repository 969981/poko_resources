"""Stream large KT FDATA records directly to source-mirrored RomFS output.

Unlike the M2 sample extractor, this does not write duplicate packed and
decoded copies. A decoded record >90 MiB is split into 80 MiB numbered parts.
One partition at a time can be committed to Git to avoid multi-GB pushes.
"""
import argparse
import csv
import hashlib
import json
import os
import tempfile
import zlib
from collections import Counter
from pathlib import Path

from .core import (FormatError, find_fdata, parse_rdb, parse_rdx, read_idrk,
                   save_csv, save_json, sha256_file)
from .publish import source_directory

MIB = 1024 * 1024


class PieceWriter:
    def __init__(self, folder, filename, expected, chunk_bytes=80 * MIB, max_single=90 * MIB):
        self.folder = Path(folder)
        self.name = filename
        self.expected = expected
        self.part_limit = chunk_bytes if expected > max_single else max_single
        self.split = expected > max_single
        self.files = []
        self.current = None
        self.current_size = 0
        self.size = 0
        self.hash = hashlib.sha256()

    def _open_next(self):
        if self.current:
            self.current.close()
        num = len(self.files) + 1
        filename = self.name + (f".part{num:04d}" if self.split else "")
        dest = self.folder / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.current = dest.open("wb")
        self.current_size = 0
        self.files.append(dest)

    def write(self, data):
        if self.size + len(data) > self.expected:
            raise FormatError("KT_DECODED_SIZE_OVERFLOW")
        self.hash.update(data)
        self.size += len(data)
        view = memoryview(data)
        while view:
            if self.current is None or self.current_size == self.part_limit:
                self._open_next()
            portion = min(len(view), self.part_limit - self.current_size)
            self.current.write(view[:portion])
            self.current_size += portion
            view = view[portion:]

    def finish(self):
        if self.current:
            self.current.close()
            self.current = None
        if self.size != self.expected:
            raise FormatError(f"KT_SIZE_MISMATCH:{self.size}:{self.expected}")
        if not self.files:
            self._open_next()
            self.current.close()
            self.current = None
        return self.hash.hexdigest()


def copy_decoded_stream(fd, header, sink):
    """Consumes the positioned IDRK payload with bounded reads and strict zlib checks."""
    if header.packed_size == header.unpacked_size:
        remaining = header.packed_size
        while remaining:
            chunk = fd.read(min(1024 * 1024, remaining))
            if not chunk:
                raise FormatError("KT_PAYLOAD_TRUNCATED")
            sink.write(chunk)
            remaining -= len(chunk)
        return
    length_bytes = 4 if header.flags & 0x100000 else 2
    header_bytes = 4 if length_bytes == 4 else 10
    consumed = 0
    while consumed < header.packed_size:
        remaining = header.packed_size - consumed
        if sink.size == header.unpacked_size and remaining <= 15:
            padding = fd.read(remaining)
            if len(padding) != remaining or any(padding):
                raise FormatError("KT_INVALID_PADDING")
            consumed += remaining
            break
        if remaining < header_bytes:
            raise FormatError("KT_TRUNCATED_CHUNK_PREFIX")
        prefix = fd.read(header_bytes)
        if len(prefix) != header_bytes:
            raise FormatError("KT_TRUNCATED_CHUNK_PREFIX")
        consumed += header_bytes
        compressed_bytes = int.from_bytes(prefix[:length_bytes], "little")
        if not compressed_bytes or compressed_bytes > header.packed_size - consumed:
            raise FormatError("KT_INVALID_CHUNK_SIZE")
        remaining_compressed = compressed_bytes
        decoder = zlib.decompressobj()
        while remaining_compressed:
            block = fd.read(min(1024 * 1024, remaining_compressed))
            if not block:
                raise FormatError("KT_COMPRESSED_BODY_TRUNCATED")
            sink.write(decoder.decompress(block))
            remaining_compressed -= len(block)
            consumed += len(block)
        sink.write(decoder.flush())
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise FormatError("KT_ZLIB_STREAM_NOT_EXACT")
    if consumed != header.packed_size:
        raise FormatError("KT_PACKED_LENGTH_MISMATCH")


def _read_prior(path):
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["record_id"]: row for row in csv.DictReader(handle)}


def run(base, out, hash_text, part_index, parts, max_total_mib, source_sha=None):
    if len(hash_text) != 8 or any(x not in "0123456789abcdef" for x in hash_text.lower()):
        raise ValueError("FDATA hash must be 8 hexadecimal digits")
    if not 0 <= part_index < parts:
        raise ValueError("Invalid partition")
    wanted = int(hash_text, 16)
    out = Path(out).resolve()
    base = Path(base).resolve()
    statuses = Counter()
    bytes_published = 0
    records_selected = 0
    updates = {}
    reports = []
    manifest_cache = {}
    for catalog in ("root", "system"):
        rdx_file = base / (catalog + ".rdx")
        rdb_file = base / (catalog + ".rdb")
        rdex = parse_rdx(rdx_file.read_bytes())
        entries, _ = parse_rdb(rdb_file.read_bytes(), catalog, rdex)
        for item in entries:
            if item.footer_magic != 0x0401 or item.footer_layout not in ("standard_13", "extended_17"):
                continue
            if item.fdata_index < 0 or rdex[item.fdata_index].fdata_hash != wanted:
                continue
            if item.record_index % parts != part_index:
                continue
            records_selected += 1
            source = find_fdata(base, rdex[item.fdata_index])
            record_id = f"{catalog}:{item.record_index}"
            row = {"source_path": "",
                   "source_sha256": source_sha or "",
                   "record_id": record_id,
                   "offset": item.fdata_offset, "stored_size": item.fdata_entry_size,
                   "unpacked_size": item.uncompressed_size,
                   "decoder_status": "", "decoder_error": "", "output_path": "",
                   "output_bytes": "", "output_sha256": "", "publish_status": "",
                   "part_count": 0}
            if source is None:
                row["publish_status"] = "CONTAINER_NOT_PRESENT"
                reports.append(row)
                statuses[row["publish_status"]] += 1
                continue
            folder = source_directory(out, "ktrdb", source, base)
            rel = source.relative_to(base)
            row["source_path"] = "2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/" + rel.as_posix()
            if not row["source_sha256"]:
                if source not in updates:
                    updates[source] = sha256_file(source)
                row["source_sha256"] = updates[source]
            if folder not in manifest_cache:
                manifest_cache[folder] = _read_prior(folder / "_manifest.csv")
            previous = manifest_cache[folder].get(record_id)
            if previous and previous.get("publish_status") in ("PUBLISHED", "ALREADY_PRESENT_VERIFIED"):
                paths = [out / p for p in previous.get("output_path", "").split(";") if p]
                same_source = previous.get("source_sha256") == row["source_sha256"]
                valid_files = bool(paths) and all(p.is_file() for p in paths)
                same_bytes = valid_files and sum(p.stat().st_size for p in paths) == int(previous.get("output_bytes") or -1)
                same_sha = (len(paths) != 1 or sha256_file(paths[0]) == previous.get("output_sha256")) if same_bytes else False
                if same_source and same_bytes and same_sha:
                    statuses["ALREADY_PRESENT_VERIFIED"] += 1
                    continue
            name = f"{catalog}_{item.record_index:06d}_{item.name_hash:08x}.fdata_idrk.bin"
            if item.uncompressed_size > max_total_mib * MIB - bytes_published:
                row["publish_status"] = "SKIPPED_BATCH_BUDGET"
                row["decoder_error"] = "Decoded record larger than remaining batch budget"
                reports.append(row)
                statuses[row["publish_status"]] += 1
                updates.setdefault(folder, {})[record_id] = row
                continue
            try:
                with source.open("rb") as f:
                    header, _ = read_idrk(f, item.fdata_offset, source.stat().st_size)
                    if (header.name_hash != item.name_hash or header.type_hash != item.type_hash
                            or header.unpacked_size != item.uncompressed_size
                            or header.entry_size != item.fdata_entry_size):
                        raise FormatError("KT_RDB_IDRK_MISMATCH")
                    with tempfile.TemporaryDirectory(prefix=".extract-", dir=folder if folder.exists() else _mkdir(folder)) as tmp:
                        sink = PieceWriter(Path(tmp), name, item.uncompressed_size)
                        try:
                            copy_decoded_stream(f, header, sink)
                            digest = sink.finish()
                        finally:
                            if sink.current:
                                sink.current.close()
                                sink.current = None
                        final_paths = []
                        for temp_file in sink.files:
                            dest = folder / "decoded" / temp_file.name
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            os.replace(temp_file, dest)
                            final_paths.append(dest.relative_to(out).as_posix())
                row["decoder_status"] = "DECOMPRESSED"
                row["publish_status"] = "PUBLISHED"
                row["output_path"] = ";".join(final_paths)
                row["output_bytes"] = item.uncompressed_size
                row["output_sha256"] = digest
                row["part_count"] = len(final_paths)
                bytes_published += item.uncompressed_size
                updates.setdefault(folder, {})
            except (FormatError, OSError, zlib.error, ValueError) as exc:
                row["publish_status"] = "DECODE_FAILED"
                row["decoder_status"] = "DECODE_FAILED"
                row["decoder_error"] = str(exc)
            reports.append(row)
            statuses[row["publish_status"]] += 1
            updates.setdefault(folder, {})[record_id] = row

    for folder, changed in list(updates.items()):
        if not isinstance(folder, Path) or not isinstance(changed, dict):
            continue
        if folder.suffix not in (".fdata", ".file"):
            continue
        prior = _read_prior(folder / "_manifest.csv")
        prior.update(changed)
        save_csv(folder / "_manifest.csv", list(prior.values()))
    report = {"hash": hash_text, "part_index": part_index, "partitions": parts,
              "selected_records": records_selected, "accepted_bytes": bytes_published,
              "statuses": dict(statuses)}
    save_json(out / "_reports" / f"ktrdb_{hash_text}_part{part_index:02d}.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False), flush=True)
    return report


def _mkdir(path):
    path.mkdir(parents=True, exist_ok=True)
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, default=Path("2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE"))
    p.add_argument("--output", type=Path, default=Path("UnPack/2.0.1"))
    p.add_argument("--hash", required=True)
    p.add_argument("--part-index", type=int, default=0)
    p.add_argument("--parts", type=int, default=1)
    p.add_argument("--max-total-mib", type=int, default=800)
    p.add_argument("--source-sha")
    args = p.parse_args()
    run(args.base, args.output, args.hash.lower(), args.part_index, args.parts,
        args.max_total_mib, args.source_sha)


if __name__ == "__main__":
    main()
