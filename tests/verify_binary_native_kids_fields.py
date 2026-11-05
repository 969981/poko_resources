#!/usr/bin/env python3
"""Independent original-byte parity check for Pokopia.Binary kids-fields NDJSON.

No game asset bytes are copied to outputs. This checks framing, hashes,
primitive widths, offsets and raw samples; it makes no semantic claims.
"""
from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

WIDTH = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 8: 4, 10: 16, 12: 8, 13: 12}


def verify(source: Path, ndjson: Path, sample_count: int = 8) -> int:
    data = source.read_bytes()
    rows = [json.loads(line) for line in ndjson.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert data[:8] == b"_DOK0000" and len(data) >= 28, "bad KIDS header"
    header_size, _platform, block_count, _hash, _size = struct.unpack_from("<5I", data, 8)
    at = (header_size + 3) & ~3
    expected = []
    for block_index in range(block_count):
        magic = data[at:at+8]
        assert magic in (b"IDOK0000", b"RDOK0000"), (block_index, magic)
        size, = struct.unpack_from("<I", data, at + 8)
        end = at + size
        assert end <= len(data)
        if magic == b"IDOK0000":
            name, typename, count = struct.unpack_from("<3I", data, at + 12)
            fields = [struct.unpack_from("<3I", data, at + 24 + i * 12)
                      for i in range(count)]
            cursor = at + 24 + count * 12
            for ordinal, (kind, item_count, field_name) in enumerate(fields):
                common = {
                    "BlockIndex": block_index, "BlockOffset": at, "BlockSize": size,
                    "BlockNameHash": name, "BlockTypeHash": typename,
                    "PropertyIndex": ordinal, "TypeCode": kind, "Count": item_count,
                    "NameHash": field_name,
                }
                if kind not in WIDTH:
                    expected.append((common, -1, 0, [], "UNSUPPORTED_TYPE_OFFSET_UNKNOWN"))
                    break
                width = WIDTH[kind]
                nbytes = item_count * width
                assert cursor + nbytes <= end, "property exceeds block"
                samples = [data[cursor+i*width:cursor+(i+1)*width].hex()
                           for i in range(min(sample_count, item_count))]
                expected.append((common, cursor, nbytes, samples, "FIXED_WIDTH_RAW_PARSED"))
                cursor += nbytes
        at = (end + 3) & ~3
    assert len(rows) == len(expected), (len(rows), len(expected))
    for i, (actual, (common, offset, nbytes, sample_hex, status)) in enumerate(zip(rows, expected)):
        for key, value in common.items():
            assert actual[key] == value, (i, key, actual[key], value)
        assert actual["ValueOffset"] == offset, (i, "offset")
        assert actual["ValueBytes"] == nbytes, (i, "length")
        assert actual["Status"] == status, (i, "status")
        assert actual["SampleRawHex"] == sample_hex, (i, "raw samples")
        assert len(actual["SamplePrimitiveValues"]) == len(sample_hex), (i, "primitive samples")
    print(f"PASS KIDS native Python/.NET parity: {source.name}, {block_count} blocks, {len(rows)} fields")
    return len(rows)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: verify_binary_native_kids_fields.py SAMPLE.kidsobjdb output.ndjson")
    verify(Path(sys.argv[1]), Path(sys.argv[2]))
