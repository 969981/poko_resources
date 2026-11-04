"""Read-only Pokopia 2.0.1 container readers (standard library only).

The extracted data can contain copyrighted game assets: keep UnPack/_work local.
This module distinguishes index, location, extraction and decompression results.
"""
from __future__ import annotations
import hashlib
import io
import json
import struct
import zlib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

INDEX_RECORD = struct.Struct('<QQQQ')
RDX_RECORD = struct.Struct('<HHI')
RDB_FOOTER = struct.Struct('<HIIHB')
IDRK_HEADER = struct.Struct('<8sQQQIIII')


class FormatError(ValueError):
    """Invalid or unsupported resource structure; callers record an error code."""


@dataclass(frozen=True)
class LinkEntry:
    index: int
    offset: int
    unpacked_size: int
    stored_size: int
    flag: int


@dataclass(frozen=True)
class RdxEntry:
    position: int
    fdata_index: int
    platform_flags: int
    fdata_hash: int

    @property
    def filename(self):
        return f'0x{self.fdata_hash:08x}.fdata'


@dataclass(frozen=True)
class RdbEntry:
    catalog: str
    record_index: int
    rdb_offset: int
    entry_size: int
    uncompressed_size: int
    name_hash: int
    type_hash: int
    flags: int
    footer_magic: int
    fdata_offset: int
    fdata_entry_size: int
    fdata_index: int
    footer_tail: int
    footer_extra_hex: str = ""
    footer_layout: str = "standard_13"


@dataclass(frozen=True)
class IdrkEntry:
    entry_size: int
    packed_size: int
    unpacked_size: int
    entry_type: int
    name_hash: int
    type_hash: int
    flags: int
    header_bytes: int


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def parse_idx(data: bytes) -> list[LinkEntry]:
    if len(data) % INDEX_RECORD.size:
        raise FormatError(f'IDX_SIZE_NOT_MULTIPLE_OF_32:{len(data)}')
    records = [LinkEntry(n, *values) for n, values in enumerate(INDEX_RECORD.iter_unpack(data))]
    for cur, nxt in zip(records, records[1:]):
        expected = cur.offset + (cur.stored_size + 255) // 256 * 256
        if nxt.offset != expected:
            raise FormatError(f'IDX_OFFSET_ALIGNMENT_MISMATCH:{cur.index}:{expected}:{nxt.offset}')
    return records


def parse_rdx(data: bytes) -> list[RdxEntry]:
    if len(data) % RDX_RECORD.size:
        raise FormatError(f'RDX_SIZE_NOT_MULTIPLE_OF_8:{len(data)}')
    return [RdxEntry(n, *vals) for n, vals in enumerate(RDX_RECORD.iter_unpack(data))]


def parse_rdb(data: bytes, catalog: str, rdx: list[RdxEntry]) -> tuple[list[RdbEntry], dict]:
    if len(data) < 32 or data[:8] != b'_DRK0000':
        raise FormatError('RDB_BAD_HEADER')
    header_size, header_unknown, advertised, header_hash = struct.unpack_from('<IIII', data, 8)
    if header_size != 32:
        raise FormatError(f'RDB_UNKNOWN_HEADER_SIZE:{header_size}')
    records = []
    at = header_size
    while at < len(data):
        if at + 48 > len(data) or data[at:at + 8] != b'IDRK0000':
            raise FormatError(f'RDB_BAD_RECORD_MAGIC:{at}')
        entry_size, payload_size, unpacked = struct.unpack_from('<QQQ', data, at + 8)
        entry_type, name_hash, type_hash, flags = struct.unpack_from('<IIII', data, at + 32)
        if entry_size < 48 + payload_size or not 13 <= payload_size <= 128 or at + entry_size > len(data):
            raise FormatError(f'RDB_BAD_ENTRY_SIZE_OR_FOOTER:{at}:{entry_size}:{payload_size}')
        footer_blob = data[at + entry_size - payload_size:at + entry_size]
        # Only 13-byte format is byte-located. Real root RDB also has 17-byte
        # and potentially other footer variants; preserve opaque bytes as-is,
        # never invent an FDATA index or offset for those records.
        if payload_size == 13:
            magic, offset, size, index, tail = RDB_FOOTER.unpack(footer_blob)
            if index >= len(rdx):
                raise FormatError(f'RDB_INVALID_RDX_POSITION:{at}:{index}')
            layout = 'standard_13'
            extra_hex = ''
        else:
            magic = int.from_bytes(footer_blob[:2], 'little')
            offset = size = 0
            index = -1
            tail = 0
            layout = f'opaque_{payload_size}'
            extra_hex = footer_blob.hex()
        records.append(RdbEntry(catalog, len(records), at, entry_size, unpacked,
                                name_hash, type_hash, flags, magic, offset, size, index, tail,
                                extra_hex, layout))
        at += (entry_size + 3) & ~3
    if len(records) != advertised or at != len(data):
        raise FormatError(f'RDB_COUNT_OR_END_MISMATCH:{len(records)}:{advertised}:{at}:{len(data)}')
    return records, {'advertised': advertised, 'parsed': len(records),
                     'header_hash': f'{header_hash:08x}', 'header_unknown': header_unknown}


def read_idrk(f: io.BufferedReader, at: int, container_size: int) -> tuple[IdrkEntry, bytes]:
    if at < 0 or at + IDRK_HEADER.size > container_size:
        raise FormatError('IDRK_OFFSET_OUT_OF_RANGE')
    f.seek(at)
    header_bytes = f.read(IDRK_HEADER.size)
    if len(header_bytes) != IDRK_HEADER.size:
        raise FormatError('IDRK_TRUNCATED_HEADER')
    magic, entry_size, packed, unpacked, etype, name, ttype, flags = IDRK_HEADER.unpack(header_bytes)
    if magic != b'IDRK0000':
        raise FormatError(f'IDRK_BAD_MAGIC:{magic.hex()}')
    if entry_size < IDRK_HEADER.size or packed > entry_size - IDRK_HEADER.size or at + entry_size > container_size:
        raise FormatError('IDRK_INVALID_LENGTH')
    metadata_len = entry_size - IDRK_HEADER.size - packed
    if metadata_len > 65536:
        raise FormatError('IDRK_EXCESSIVE_METADATA')
    metadata = f.read(metadata_len)
    if len(metadata) != metadata_len:
        raise FormatError('IDRK_METADATA_TRUNCATED')
    return IdrkEntry(entry_size, packed, unpacked, etype, name, ttype, flags, metadata_len), metadata


def kt_zlib_chunks(data: bytes, expected_size: int, flags: int) -> bytes:
    """KT framed zlib: either u32 length or u16 length + 8-byte field, per chunk.

    Uses strict zlib stream checks. Does not silently emit partial results.
    """
    out = bytearray()
    pos = 0
    header_size = 4 if flags & 0x100000 else 10
    while pos < len(data):
        # KT may pad the final compressed chunk to a record boundary.
        if len(out) == expected_size and len(data) - pos <= 15 and not any(data[pos:]):
            pos = len(data)
            break
        if pos + header_size > len(data):
            raise FormatError('KT_TRUNCATED_CHUNK_HEADER')
        chunk_len = int.from_bytes(data[pos:pos + (4 if header_size == 4 else 2)], 'little')
        pos += header_size
        if not chunk_len or pos + chunk_len > len(data):
            raise FormatError('KT_BAD_COMPRESSED_CHUNK_LENGTH')
        decoder = zlib.decompressobj()
        block = decoder.decompress(data[pos:pos + chunk_len], expected_size - len(out) + 1)
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise FormatError('KT_INVALID_ZLIB_STREAM')
        out.extend(block)
        pos += chunk_len
        if len(out) > expected_size:
            raise FormatError('KT_DECOMPRESSED_SIZE_OVERFLOW')
    if len(out) != expected_size:
        raise FormatError(f'KT_DECOMPRESSED_SIZE_MISMATCH:{len(out)}:{expected_size}')
    return bytes(out)


def decode_kt_payload(data: bytes, header: IdrkEntry) -> bytes:
    if len(data) != header.packed_size:
        raise FormatError('KT_TRUNCATED_DATA')
    if header.packed_size == header.unpacked_size:
        return data
    return kt_zlib_chunks(data, header.unpacked_size, header.flags)


def _strict_zlib_stream(data: bytes, remaining: int, error_prefix: str) -> bytes:
    try:
        d = zlib.decompressobj()
        content = d.decompress(data, remaining + 1)
    except zlib.error as exc:
        raise FormatError(f'{error_prefix}_ZLIB_ERROR:{exc}') from exc
    if not d.eof or d.unused_data or d.unconsumed_tail:
        raise FormatError(f'{error_prefix}_ZLIB_NOT_SINGLE_COMPLETE_STREAM')
    if len(content) > remaining:
        raise FormatError(f'{error_prefix}_DECOMPRESSED_SIZE_OVERFLOW')
    return content


def decode_linkdata_payload(data: bytes, expected_size: int, flag: int) -> bytes:
    """LINKDATA v2.0.1: 0x80-byte header, 64-KiB chunk table, framed zlib.

    The record is 256-byte aligned in BIN. Each chunk is preceded by a u32
    compressed byte count, and each stored chunk extent is rounded to 0x80.
    Standard naked zlib is retained for synthetic/other-version test fixtures.
    """
    if flag == 0:
        if len(data) != expected_size:
            raise FormatError('LINK_RAW_SIZE_MISMATCH')
        return data
    if flag != 1:
        raise FormatError(f'LINK_UNKNOWN_CODEC_FLAG:{flag}')
    if len(data) < 0x80:
        return _strict_zlib_stream(data, expected_size, 'LINK_RAW')
    chunk_size, count, advertised = struct.unpack_from('<III', data)
    if not (chunk_size in (0x10000, 0x20000, 0x40000, 0x80000, 0x100000)
            and 1 <= count <= 512 and count == (expected_size + chunk_size - 1) // chunk_size):
        # Do not blindly search for zlib headers at arbitrary offsets.
        return _strict_zlib_stream(data, expected_size, 'LINK_DIRECT')
    if advertised != expected_size:
        raise FormatError(f'LINK_HEADER_UNPACKED_SIZE_MISMATCH:{advertised}:{expected_size}')
    header_size = ((12 + 4 * count + 127) // 128) * 128
    if len(data) < header_size:
        raise FormatError('LINK_CHUNK_TABLE_TRUNCATED')
    stored_extents = struct.unpack_from('<' + 'I' * count, data, 12)
    decoded = bytearray()
    cursor = header_size
    for i, extent in enumerate(stored_extents):
        if extent < 4 or cursor + extent > len(data):
            raise FormatError(f'LINK_CHUNK_BOUNDS:{i}:{cursor}:{extent}:{len(data)}')
        packed_size = struct.unpack_from('<I', data, cursor)[0]
        remaining = expected_size - len(decoded)
        if not packed_size and extent == min(chunk_size, remaining):
            # Observed tiny, uncompressed final chunks (16/18 bytes) have no
            # 4-byte length prefix. Verify exact chunk extent and output size.
            block = data[cursor:cursor + extent]
        else:
            if not packed_size or packed_size + 4 > extent:
                raise FormatError(f'LINK_CHUNK_PACKED_SIZE_INVALID:{i}:{packed_size}:{extent}')
            block = _strict_zlib_stream(data[cursor + 4:cursor + 4 + packed_size],
                                        remaining, 'LINK_CHUNK')
        decoded.extend(block)
        cursor += ((extent + 0x7f) // 0x80) * 0x80
    if len(decoded) != expected_size:
        raise FormatError(f'LINK_TOTAL_UNPACKED_SIZE_MISMATCH:{len(decoded)}:{expected_size}')
    if cursor > len(data):
        raise FormatError(f'LINK_FINAL_CHUNK_OVERRUN:{cursor}:{len(data)}')
    return bytes(decoded)


def find_fdata(base: Path, entry: RdxEntry) -> Path | None:
    # Don't infer ff03 means missing; inspect all known platform roots.
    roots = [base, base / 'MountPoint_1', base / 'MountPoint_2']
    expected = {0xffff: base, 0xff01: roots[1], 0xff02: roots[2]}.get(entry.platform_flags)
    if expected and (expected / entry.filename).is_file():
        return expected / entry.filename
    hits = [root / entry.filename for root in roots if (root / entry.filename).is_file()]
    return hits[0] if len(hits) == 1 else None


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def save_csv(path: Path, records: list[dict]) -> None:
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        path.write_text('', encoding='utf-8')
        return
    keys = sorted(set().union(*(row.keys() for row in records)))
    with path.open('w', encoding='utf-8', newline='') as out:
        w = csv.DictWriter(out, fieldnames=keys)
        w.writeheader()
        w.writerows(records)
