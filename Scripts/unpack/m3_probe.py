"""M3 prefix-only content signature survey of real Pokopia 2.0.1 assets.

Reads a bounded byte prefix directly from original IDRK / LINKDATA containers:
no 18-GB re-download of already published decoded Git blobs, no guessed
extensions, and no claims of complete texture/model/FlatBuffers conversion.

Output is *evidence*, not a semantic decoder. The M2 verification did full
decode+hash previously; this sampler intentionally does NOT verify full payload.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import struct
import zlib
from collections import Counter
from pathlib import Path

from .core import FormatError, parse_idx, parse_rdb, parse_rdx, read_idrk, save_csv, save_json

MIB = 1024 * 1024
MAX_COMPRESSED_PEEK = 2 * MIB
PREFIX = 96


def classify(head: bytes, total_bytes: int):
    if not head:
        return "EMPTY", "EXACT", ""
    if head.startswith(b"_DOK0000"):
        return "KIDSOBJDB_SIGNATURE", "HIGH", ".kidsobjdb"
    if head.startswith((b"G1M_", b"_M1G")):
        return "G1M_MODEL_CONTAINER", "HIGH", ".g1m"
    if head.startswith((b"G1TG", b"G1T_", b"_T1G")):
        return "G1T_TEXTURE_CONTAINER", "HIGH", ".g1t"
    if head.startswith((b"G1A_", b"_A1G")):
        return "G1A_ANIMATION_CONTAINER", "HIGH", ".g1a"
    if len(head) >= 8 and head[4:8] == b"BFBS" and 8 <= int.from_bytes(head[:4], "little") < total_bytes:
        return "FLATBUFFERS_SCHEMA_BFBS", "HIGH", ".bfbs"
    if head.startswith(b"BNTX"):
        return "BNTX_TEXTURE_CONTAINER", "HIGH", ".bntx"
    if head.startswith(b"NVN"):
        return "NVN_CANDIDATE", "MEDIUM", ""
    if head.startswith(b"DDS "):
        return "DDS_TEXTURE", "HIGH", ".dds"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "PNG_IMAGE", "HIGH", ".png"
    if head.startswith(b"SQLite format 3\x00"):
        return "SQLITE_DATABASE", "HIGH", ".sqlite"
    if head.startswith(b"\xabKTX 11\xbb\r\n\x1a\n") or head.startswith(b"\xabKTX 20\xbb\r\n\x1a\n"):
        return "KTX_TEXTURE", "HIGH", ".ktx"
    if head.startswith(b"RIFF") and len(head) > 12 and head[8:12] == b"WAVE":
        return "RIFF_WAVE_AUDIO", "HIGH", ".wav"
    if head.startswith((b"CRILAYLA", b"@UTF")):
        return "CRI_AUDIO_OR_CONTAINER", "HIGH", ""
    if head.startswith(b"PK\x03\x04"):
        return "ZIP_CONTAINER", "HIGH", ".zip"
    if head.startswith(b"\x1f\x8b\x08"):
        return "GZIP_COMPRESSED", "HIGH", ".gz"
    if head.startswith(b"\x7fELF"):
        return "ELF_BINARY", "HIGH", ".elf"
    stripped = head.lstrip(b"\xef\xbb\xbf \r\n\t")
    if stripped[:1] in (b"{", b"["):
        try:
            sample = head.decode("utf-8")
            if all((ord(c) >= 32 or c in "\t\n\r") for c in sample):
                return "JSON_CANDIDATE", "MEDIUM", ".json"
        except UnicodeDecodeError:
            pass
    if stripped.startswith(b"<?xml"):
        return "XML_CANDIDATE", "MEDIUM", ".xml"
    if len(head) >= 16 and all(32 <= b < 127 or b in (9, 10, 13) for b in head[:min(64, len(head))]):
        return "PRINTABLE_TEXT_CANDIDATE", "LOW", ""
    return "UNKNOWN_BINARY", "NONE", ""


def _zlib_peek(fragment: bytes, cap: int = PREFIX):
    try:
        return zlib.decompressobj().decompress(fragment, cap)
    except zlib.error as e:
        raise FormatError("M3_PEEK_ZLIB:" + str(e)) from e


def peek_idrk(fd, header, length=PREFIX):
    """fd is immediately after IDRK header/metadata; bounded first-chunk probe."""
    if header.unpacked_size == 0:
        return b""
    if header.packed_size == header.unpacked_size:
        return fd.read(min(length, header.packed_size))
    prefix_bytes = 4 if header.flags & 0x100000 else 10
    flag_bytes = 4 if prefix_bytes == 4 else 2
    prefix = fd.read(prefix_bytes)
    if len(prefix) != prefix_bytes:
        raise FormatError("M3_TRUNCATED_KT_CHUNK_PREFIX")
    packed = int.from_bytes(prefix[:flag_bytes], "little")
    if packed <= 0 or packed > header.packed_size - prefix_bytes:
        raise FormatError("M3_KT_FIRST_CHUNK_SIZE_INVALID")
    fragment = fd.read(min(packed, MAX_COMPRESSED_PEEK))
    return _zlib_peek(fragment, length)


def peek_link(fd, entry, length=PREFIX):
    if not entry.stored_size:
        return b""
    fd.seek(entry.offset)
    if entry.flag == 0:
        return fd.read(min(length, entry.unpacked_size))
    if entry.flag != 1:
        raise FormatError("M3_LINK_FLAG_UNSUPPORTED")
    first = fd.read(min(entry.stored_size, 4096))
    if len(first) < 12:
        raise FormatError("M3_LINK_HEADER_TOO_SHORT")
    chunk_size, count, total = struct.unpack_from("<III", first)
    if count == 0 and entry.unpacked_size == 0:
        return b""
    if chunk_size not in (0x10000, 0x20000, 0x40000, 0x80000, 0x100000) or not 1 <= count <= 512:
        return _zlib_peek(first, length)
    if total != entry.unpacked_size:
        raise FormatError("M3_LINK_HEADER_SIZE_MISMATCH")
    header_size = (12 + 4 * count + 127) // 128 * 128
    if len(first) < 12 + 4 * count:
        fd.seek(entry.offset)
        first = fd.read(min(entry.stored_size, max(4096, 12 + 4 * count)))
        if len(first) < 12 + 4 * count:
            raise FormatError("M3_LINK_CHUNK_TABLE_TRUNCATED")
    extent = struct.unpack_from("<I", first, 12)[0]
    fd.seek(entry.offset + header_size)
    compressed_length = fd.read(4)
    if len(compressed_length) < 4:
        raise FormatError("M3_LINK_FIRST_CHUNK_TRUNCATED")
    packed = struct.unpack("<I", compressed_length)[0]
    if (packed == 0 or packed + 4 > extent) and extent == min(chunk_size, entry.unpacked_size) and extent <= 32:
        fd.seek(entry.offset + header_size)
        return fd.read(min(length, extent))
    if packed <= 0 or packed + 4 > extent:
        raise FormatError("M3_LINK_FIRST_CHUNK_INVALID")
    return _zlib_peek(fd.read(min(packed, MAX_COMPRESSED_PEEK)), length)


def run_kt(base: Path, source: Path, target: Path):
    base, source = Path(base), Path(source)
    if source.suffix not in (".fdata", ".file") or not source.is_file():
        raise ValueError("M3_KT_SOURCE_NOT_RESTORED")
    match = re.fullmatch(r"0x([0-9a-fA-F]{8})\.(?:file|fdata)", source.name)
    if not match:
        raise ValueError("M3_INVALID_KT_SOURCE_NAME")
    wanted = int(match.group(1), 16)
    chosen = []
    for catalog in ("root", "system"):
        rdx = parse_rdx((base / (catalog + ".rdx")).read_bytes())
        records, _ = parse_rdb((base / (catalog + ".rdb")).read_bytes(), catalog, rdx)
        for r in records:
            if r.footer_layout not in ("standard_13", "extended_17"):
                continue
            if source.suffix == ".fdata":
                if r.footer_magic != 0x0401 or r.fdata_index < 0 or rdx[r.fdata_index].fdata_hash != wanted:
                    continue
            else:
                if r.footer_magic != 0x0c01 or r.name_hash != wanted:
                    continue
            chosen.append((catalog, r))
    if not chosen:
        raise ValueError("M3_SOURCE_HAS_NO_RDB_RECORDS")
    results = []
    with source.open("rb") as fd:
        for catalog, r in chosen:
            row = {"source": str(source), "record_id": f"{catalog}:{r.record_index}",
                   "catalog": catalog, "record_index": r.record_index,
                   "name_hash": f"{r.name_hash:08x}", "type_hash": f"{r.type_hash:08x}",
                   "unpacked_size": r.uncompressed_size, "stored_size": r.fdata_entry_size,
                   "offset": r.fdata_offset if source.suffix == ".fdata" else 0,
                   "head_64_hex": "", "magic_ascii": "", "signature": "",
                   "confidence": "", "candidate_extension": "", "status": "", "error": ""}
            try:
                start = r.fdata_offset if source.suffix == ".fdata" else 0
                header, _ = read_idrk(fd, start, source.stat().st_size)
                if (header.name_hash != r.name_hash or header.type_hash != r.type_hash or
                        header.unpacked_size != r.uncompressed_size or header.entry_size != r.fdata_entry_size):
                    raise FormatError("M3_RDB_IDRK_MISMATCH")
                head = peek_idrk(fd, header)
                kind, confidence, ext = classify(head, header.unpacked_size)
                row.update(head_64_hex=head[:64].hex(),
                           magic_ascii="".join(chr(x) if 32 <= x < 127 else "." for x in head[:16]),
                           signature=kind, confidence=confidence,
                           candidate_extension=ext, status="PROBED")
            except (FormatError, OSError, zlib.error, ValueError) as e:
                row.update(status="PROBE_FAILED", error=str(e))
            results.append(row)
    return write_results(results, target)


def run_link(idx: Path, source: Path, target: Path):
    entries = parse_idx(Path(idx).read_bytes())
    results = []
    with Path(source).open("rb") as fd:
        for e in entries:
            row = {"source": str(source), "record_id": f"link:{e.index}",
                   "catalog": "link", "record_index": e.index,
                   "name_hash": "", "type_hash": "", "unpacked_size": e.unpacked_size,
                   "stored_size": e.stored_size, "offset": e.offset,
                   "head_64_hex": "", "magic_ascii": "", "signature": "",
                   "confidence": "", "candidate_extension": "", "status": "", "error": ""}
            if not e.stored_size:
                row.update(signature="EMPTY_INDEX", confidence="EXACT", status="EMPTY_INDEX")
                results.append(row)
                continue
            try:
                head = peek_link(fd, e)
                kind, confidence, ext = classify(head, e.unpacked_size)
                row.update(head_64_hex=head[:64].hex(),
                           magic_ascii="".join(chr(x) if 32 <= x < 127 else "." for x in head[:16]),
                           signature=kind, confidence=confidence,
                           candidate_extension=ext, status="PROBED")
            except (FormatError, OSError, zlib.error, ValueError) as err:
                row.update(status="PROBE_FAILED", error=str(err))
            results.append(row)
    return write_results(results, target)


def write_results(rows: list[dict], target: Path):
    target = Path(target)
    save_csv(target.with_suffix(".csv"), rows)
    counters = Counter(r["signature"] for r in rows)
    statuses = Counter(r["status"] for r in rows)
    result = {"records": len(rows), "signatures": dict(counters),
              "statuses": dict(statuses),
              "caveat": "Only bounded decoded HEAD bytes were inspected; no semantic conversion."}
    save_json(target.with_suffix(".json"), result)
    print(json.dumps({"output": str(target), **result}, ensure_ascii=False), flush=True)
    if statuses.get("PROBE_FAILED"):
        raise RuntimeError(f"M3_PREFIX_PROBE_FAILED:{statuses['PROBE_FAILED']}")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", required=True, choices=("ktrdb", "link"))
    p.add_argument("--base", type=Path, default=Path("2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE"))
    p.add_argument("--source", required=True, type=Path)
    p.add_argument("--idx", type=Path, default=Path("2.0.1/romfs/LI_C0_R.IDX"))
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    if args.kind == "ktrdb":
        run_kt(args.base, args.source, args.output)
    else:
        run_link(args.idx, args.source, args.output)


if __name__ == "__main__":
    main()
