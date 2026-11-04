"""Bounded Pokopia/Koei Tecmo KIDSOBJDB structural decoder (M4 candidate).

Reads real _DOK/IDOK/RDOK blocks; parses the supported fixed-width property
types. An unsupported type or RDOK is explicitly marked PARTIAL, never
invented as a decoded property. Built from observed format structures and
validated against native Pokopia game payloads with guardrails.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

from .core import FormatError, save_json

STRUCTS = {
    0: ("<b", 1), 1: ("<B", 1), 2: ("<h", 2), 3: ("<H", 2),
    4: ("<i", 4), 5: ("<I", 4), 8: ("<f", 4),
    10: ("<4f", 16), 12: ("<2f", 8), 13: ("<3f", 12),
}
HEADER_BYTES = 28
MAX_BLOCKS = 2_000_000
MAX_PROPS_PER_BLOCK = 65536
MAX_SAMPLED_VALUES = 1024


def _u32(blob: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(blob):
        raise FormatError("KIDSOBJDB_TRUNCATED_U32")
    return struct.unpack_from("<I", blob, offset)[0]


def parse(blob: bytes, max_sampled_values: int = 32) -> dict:
    if len(blob) < HEADER_BYTES or blob[:8] != b"_DOK0000":
        raise FormatError("KIDSOBJDB_INVALID_HEADER")
    if max_sampled_values < 0 or max_sampled_values > MAX_SAMPLED_VALUES:
        raise ValueError("KIDSOBJDB_INVALID_SAMPLE_LIMIT")
    header_size, platform, entries, name_hash, declared_size = struct.unpack_from("<5I", blob, 8)
    if header_size < HEADER_BYTES or header_size > len(blob):
        raise FormatError("KIDSOBJDB_INVALID_HEADER_SIZE")
    if entries > MAX_BLOCKS:
        raise FormatError("KIDSOBJDB_TOO_MANY_BLOCKS")
    offset = (header_size + 3) & ~3
    blocks, summary, unexpected = [], {"IDOK": 0, "RDOK": 0, "UNSUPPORTED_TYPES": 0, "PARTIAL_BLOCKS": 0}, []
    for index in range(entries):
        if offset + 12 > len(blob):
            raise FormatError(f"KIDSOBJDB_BLOCK_HEADER_TRUNCATED:{index}:{offset}")
        magic = blob[offset:offset + 8]
        if magic not in (b"IDOK0000", b"RDOK0000"):
            raise FormatError(f"KIDSOBJDB_BLOCK_MAGIC_UNKNOWN:{index}:{offset}:{magic.hex()}")
        kind = magic[:4].decode("ascii")
        size = _u32(blob, offset + 8)
        minimum = 24 if kind == "IDOK" else 12
        if size < minimum or offset + size > len(blob):
            raise FormatError(f"KIDSOBJDB_BLOCK_SIZE_INVALID:{index}:{offset}:{size}")
        end = offset + size
        entry = {
            "index": index, "kind": kind, "offset": offset,
            "size": size, "sha256": hashlib.sha256(blob[offset:end]).hexdigest(),
            "status": "STRUCTURE_ONLY",
        }
        if kind == "IDOK":
            prop_name, prop_typename, prop_count = struct.unpack_from("<3I", blob, offset + 12)
            if prop_count > MAX_PROPS_PER_BLOCK or 24 + prop_count * 12 > size:
                raise FormatError(f"KIDSOBJDB_PROPERTY_HEADER_INVALID:{index}")
            entry.update(name_hash=f"{prop_name:08x}", type_hash=f"{prop_typename:08x}",
                         property_count=prop_count, properties=[])
            cursor = offset + 24
            fields = []
            for p in range(prop_count):
                field_kind, field_count, field_hash = struct.unpack_from("<3I", blob, cursor)
                if field_count > 1_000_000:
                    raise FormatError(f"KIDSOBJDB_PROPERTY_COUNT_LIMIT:{index}:{p}")
                fields.append((field_kind, field_count, field_hash))
                cursor += 12
            partial = False
            for ordinal, (field_kind, field_count, field_hash) in enumerate(fields):
                field = {"index": ordinal, "type_code": field_kind,
                         "name_hash": f"{field_hash:08x}", "count": field_count}
                if field_kind not in STRUCTS:
                    field.update(status="UNSUPPORTED_TYPE", error="Unrecognized KIDSOBJDB field representation")
                    entry["properties"].append(field)
                    summary["UNSUPPORTED_TYPES"] += 1
                    partial = True
                    break
                format_text, element_size = STRUCTS[field_kind]
                if field_count * element_size > end - cursor:
                    raise FormatError(f"KIDSOBJDB_PROPERTY_DATA_TRUNCATED:{index}:{ordinal}")
                values = []
                for n in range(min(max_sampled_values, field_count)):
                    parts = struct.unpack_from(format_text, blob, cursor + element_size * n)
                    values.append(parts[0] if len(parts) == 1 else list(parts))
                cursor += field_count * element_size
                field.update(status="DECODED_FIXED_WIDTH",
                             value_bytes=field_count * element_size, sample_values=values)
                entry["properties"].append(field)
            if partial:
                entry["status"] = "PARTIAL_UNSUPPORTED_PROPERTY"
                summary["PARTIAL_BLOCKS"] += 1
            else:
                entry["status"] = "FIXED_WIDTH_VALUES_PARSED"
                # Allow nonzero trailing bytes, but document their existence.
                if cursor < end:
                    extra = blob[cursor:end]
                    entry["trailing_bytes"] = len(extra)
                    entry["trailing_nonzero"] = sum(v != 0 for v in extra)
        else:
            # RDOK data model is not established; preserve its shape+hash.
            entry["status"] = "RDOK_OPAQUE"
            entry["payload_bytes"] = size - 12
            summary["PARTIAL_BLOCKS"] += 1
        blocks.append(entry)
        summary[kind] += 1
        offset = (end + 3) & ~3
    if offset != len(blob):
        unexpected.append(f"UNACCOUNTED_TRAILING_BYTES:{len(blob) - offset}")
        if offset > len(blob):
            raise FormatError("KIDSOBJDB_ALIGNED_BLOCK_OVERRUN")
    if declared_size and declared_size != len(blob):
        unexpected.append(f"DECLARED_SIZE_MISMATCH:{declared_size}:{len(blob)}")
    return {
        "magic": "_DOK0000", "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "header": {
            "header_size": header_size, "platform": platform,
            "entry_count": entries, "name_file_hash": f"{name_hash:08x}",
            "declared_size": declared_size,
        },
        "summary": summary, "warnings": unexpected, "blocks": blocks,
        "semantic_status": "FIXED_WIDTH_ONLY" if summary["PARTIAL_BLOCKS"] == 0 else "PARTIAL_UNSUPPORTED_OR_RDOK",
    }


def run(path: Path, output: Path, max_sampled_values=32, max_mib=64):
    path = Path(path)
    if path.stat().st_size > max_mib * 1024**2:
        raise ValueError("KIDSOBJDB_FILE_EXCEEDS_SAFETY_LIMIT")
    result = parse(path.read_bytes(), max_sampled_values)
    save_json(Path(output), result)
    print(json.dumps({
        "source": str(path), "records": result["header"]["entry_count"],
        "summary": result["summary"], "semantic_status": result["semantic_status"],
        "warnings": result["warnings"],
    }, ensure_ascii=False), flush=True)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--max-sampled-values", type=int, default=32)
    p.add_argument("--max-mib", type=int, default=64)
    a = p.parse_args()
    run(a.input, a.output, a.max_sampled_values, a.max_mib)


if __name__ == "__main__":
    main()
