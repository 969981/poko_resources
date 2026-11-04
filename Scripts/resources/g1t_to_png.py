#!/usr/bin/env python3
"""M5 exploratory Pokopia G1T -> BC7/BC3 PNG previews and TEXINFO name index.

Outputs are candidates, NOT verified texture-to-item matches. No RomFS input is modified.
Requires Pillow >= 10 with the BC7 DDS decoder.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import struct
from pathlib import Path

from PIL import Image

TEXINFO_NAME = re.compile(r"^[\w.\-/]{1,63}$", re.ASCII)
ITEM_NAME = re.compile(r"^item_(\d+)(?:_|$)", re.IGNORECASE)
FIELDS = ["g1t_path", "texture_index", "layout", "platform", "format", "width", "height", "png_path", "png_sha256", "status", "reason"]


def u32(data: bytes, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"truncated u32 at {offset:#x}")
    return struct.unpack_from("<I", data, offset)[0]


def parse_g1t(data: bytes) -> tuple[int, list[dict]]:
    if len(data) < 0x20 or data[:4] != b"GT1G" or data[4:8] != b"0600":
        raise ValueError("unsupported G1T signature/version; expected GT1G0600")
    declared, table, count, platform = struct.unpack_from("<IIII", data, 8)
    if declared != len(data):
        raise ValueError(f"G1T declared {declared} bytes but file has {len(data)}")
    if not (0 < count <= 4096) or table < 0x1c or table + count * 4 > len(data):
        raise ValueError("invalid G1T offset table")
    offsets = [u32(data, table + i * 4) for i in range(count)]
    results = []
    for i, rel in enumerate(offsets):
        start = table + rel
        end = table + offsets[i + 1] if i + 1 < count else len(data)
        if not (table + count * 4 <= start < end <= len(data)) or start + 8 > end:
            raise ValueError(f"invalid texture[{i}] range")
        mip_sys, fmt, dxdy, _, _, _, _, ext_ver = data[start:start + 8]
        width, height = 1 << (dxdy & 15), 1 << (dxdy >> 4)
        extra_size = u32(data, start + 8) if ext_ver else 0
        if extra_size and (extra_size < 12 or extra_size > 4096):
            raise ValueError(f"invalid texture[{i}] extra header size: {extra_size}")
        if extra_size >= 16:
            width = u32(data, start + 20)
        if extra_size >= 20:
            height = u32(data, start + 24)
        payload_start = start + 8 + extra_size
        if width < 1 or height < 1 or width > 16384 or height > 16384 or payload_start > end:
            raise ValueError(f"invalid texture[{i}] dimensions/payload")
        results.append({"format": fmt, "width": width, "height": height,
                        "mip_count": mip_sys >> 4, "payload": data[payload_start:end]})
    return platform, results


def unswizzle_gob_bc7(src: bytes, width: int, height: int, gob_height: int) -> bytes:
    """Tegra 64x8 GOB block-linear -> row-major BC7 blocks (16 bytes each)."""
    if gob_height not in (1, 2, 4, 8, 16, 32):
        raise ValueError("GOB height must be power of two in [1,32]")
    bw, bh = (width + 3) // 4, (height + 3) // 4
    stride = ((bw * 16 + 63) // 64) * 64
    columns = stride // 64
    required = ((bh + 8 * gob_height - 1) // (8 * gob_height)) * columns * 512 * gob_height
    if len(src) < required:
        raise ValueError(f"GOB layout requires {required} bytes, found {len(src)}")
    dst = bytearray(bw * bh * 16)
    for y in range(bh):
        for x in range(bw):
            byte_x = x * 16
            block = y // (8 * gob_height)
            row_in_block = y % (8 * gob_height)
            gob_base = ((block * columns + byte_x // 64) * gob_height + row_in_block // 8) * 512
            row = row_in_block % 8
            for k in range(16):
                bx = (byte_x + k) % 64
                inner = ((bx & 32) << 3) | ((row & 4) << 5) | ((row & 2) << 5) | \
                        ((bx & 16) << 1) | ((row & 1) << 4) | (bx & 15)
                dst[(y * bw + x) * 16 + k] = src[gob_base + inner]
    return bytes(dst)


def unswizzle_morton_bc(src: bytes, width: int, height: int,
                         tile_blocks: int = 0, swap_axes: bool = False) -> bytes:
    """Explore Morton/Z-order compressed BC block arrangements.

    tile_blocks=0: full-image Morton (square power-of-two block grid).
    tile_blocks>0: tiles in row-major order, Morton blocks within each tile.
    These are unverified candidate permutations, not inferred native formats.
    """
    bw, bh = (width + 3) // 4, (height + 3) // 4
    if bw <= 0 or bh <= 0 or (bw & (bw - 1)) or (bh & (bh - 1)):
        raise ValueError("Morton candidate needs power-of-two BC block dimensions")
    if tile_blocks == 0:
        if bw != bh:
            raise ValueError("global Morton requires square BC block image")
        tile_blocks = bw
    if tile_blocks <= 0 or (tile_blocks & (tile_blocks - 1)):
        raise ValueError("Morton tile dimension must be a power of two")
    if bw % tile_blocks or bh % tile_blocks:
        raise ValueError("Morton tile does not divide BC block dimensions")
    blocks = bw * bh
    if len(src) < blocks * 16:
        raise ValueError(f"Morton candidate needs {blocks * 16} source bytes")
    levels = tile_blocks.bit_length() - 1
    dst = bytearray(blocks * 16)
    tiles_w = bw // tile_blocks
    for y in range(bh):
        for x in range(bw):
            tx, ty = x // tile_blocks, y // tile_blocks
            ix, iy = x % tile_blocks, y % tile_blocks
            if swap_axes:
                ix, iy = iy, ix
            z = 0
            for bit in range(levels):
                z |= ((ix >> bit) & 1) << (bit * 2)
                z |= ((iy >> bit) & 1) << (bit * 2 + 1)
            source_block = ((ty * tiles_w + tx) * tile_blocks * tile_blocks) + z
            dst[(y * bw + x) * 16:(y * bw + x + 1) * 16] = src[source_block * 16:(source_block + 1) * 16]
    return bytes(dst)


def make_bc7_dds(data: bytes, width: int, height: int) -> bytes:
    expected = ((width + 3) // 4) * ((height + 3) // 4) * 16
    if len(data) < expected:
        raise ValueError(f"BC7 needs {expected} bytes, has {len(data)}")
    header = bytearray(148)
    header[:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x81007)
    struct.pack_into("<II", header, 12, height, width)
    struct.pack_into("<I", header, 20, expected)
    struct.pack_into("<I", header, 76, 32)
    struct.pack_into("<I", header, 80, 4)
    header[84:88] = b"DX10"
    struct.pack_into("<I", header, 108, 0x1000)
    struct.pack_into("<IIIII", header, 128, 98, 3, 0, 1, 0)
    return bytes(header) + data[:expected]


def make_bc3_dds(data: bytes, width: int, height: int) -> bytes:
    expected = ((width + 3) // 4) * ((height + 3) // 4) * 16
    if len(data) < expected:
        raise ValueError(f"BC3 needs {expected} bytes, has {len(data)}")
    header = bytearray(128)
    header[:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<I", header, 8, 0x81007)
    struct.pack_into("<II", header, 12, height, width)
    struct.pack_into("<I", header, 20, expected)
    struct.pack_into("<I", header, 76, 32)
    struct.pack_into("<I", header, 80, 4)
    header[84:88] = b"DXT5"
    struct.pack_into("<I", header, 108, 0x1000)
    return bytes(header) + data[:expected]


def decode_png(payload: bytes, width: int, height: int, layout: str, fmt: int = 0x66) -> bytes:
    if layout == "linear":
        linear = payload
    elif layout.startswith("gob"):
        linear = unswizzle_gob_bc7(payload, width, height, int(layout[3:]))
    elif layout.startswith("morton"):
        kind = layout.removeprefix("morton")
        swap_axes = kind.endswith("_yx")
        kind = kind.removesuffix("_yx")
        if kind and not kind.isdigit():
            raise ValueError(f"invalid Morton candidate layout {layout}")
        linear = unswizzle_morton_bc(payload, width, height, int(kind) if kind else 0, swap_axes)
    else:
        raise ValueError(f"unsupported layout {layout}")
    if fmt in (0x66, 0x5f):
        dds = make_bc7_dds(linear, width, height)
    elif fmt in (0x62, 0x5b, 0x08, 0x12):
        dds = make_bc3_dds(linear, width, height)
    else:
        raise ValueError(f"unsupported BC texture format {fmt:#x}")
    with Image.open(io.BytesIO(dds)) as image:
        image.load()
        if image.size != (width, height):
            raise ValueError("decoded image dimensions do not match")
        out = io.BytesIO()
        image.convert("RGBA").save(out, format="PNG")
        return out.getvalue()


TEXINFO_RECORD_SIZE = 104


def parse_texinfo(data: bytes) -> list[dict]:
    """Parse all TEXINFO records, including packed sprite atlases.

    Format: <u32 record_count> followed by record_count * 104 bytes.
    Each entry holds a 64-byte ASCII name, two u32 fields and eight
    little-endian float32 UV corner coordinates. This does not prove
    which G1T contains the texture: that link needs separate evidence.
    """
    if len(data) < 4:
        raise ValueError("truncated TEXINFO header")
    count = u32(data, 0)
    if not 1 <= count <= 65536 or len(data) != 4 + count * TEXINFO_RECORD_SIZE:
        raise ValueError(
            f"TEXINFO record count/size mismatch: count={count}, bytes={len(data)}"
        )
    records = []
    for idx in range(count):
        start = 4 + idx * TEXINFO_RECORD_SIZE
        name_bytes = data[start:start + 64].split(b"\x00", 1)[0]
        try:
            name = name_bytes.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError(f"non-ASCII name in TEXINFO record {idx}") from exc
        if not TEXINFO_NAME.fullmatch(name):
            raise ValueError(f"invalid TEXINFO name in record {idx}: {name!r}")
        layer = u32(data, start + 64)
        quad = struct.unpack_from("<8f", data, start + 68)
        tail = u32(data, start + 100)
        import math
        if not all(math.isfinite(v) for v in quad):
            raise ValueError(f"non-finite UV in TEXINFO record {idx}")
        u0, v0, u1, v0b, u0b, v1, u1b, v1b = quad
        rectangular = (abs(v0 - v0b) < 1e-5 and
                       abs(u0 - u0b) < 1e-5 and
                       abs(u1 - u1b) < 1e-5 and
                       abs(v1 - v1b) < 1e-5 and
                       -1e-5 <= u0 <= u1 <= 1.00001 and
                       -1e-5 <= v0 <= v1 <= 1.00001)
        records.append({
            "name": name, "record_index": idx, "record_count": count,
            "u0": u0, "v0": v0, "u1": u1, "v1": v1,
            "uv_status": "RECT_OK" if rectangular else "NONRECT_OR_OUT_OF_RANGE",
            "texture_layer_raw_u32": layer, "record_tail_raw_u32": tail,
        })
    return records


def texinfo_index(root: Path, output: Path) -> int:
    """Write one row per TEXINFO sprite, not one row per TEXINFO file."""
    fields = [
        "texinfo_path", "texture_name", "family", "item_id_candidate", "link_status",
        "record_index", "record_count", "atlas_u0", "atlas_v0",
        "atlas_u1", "atlas_v1", "uv_status",
        "texture_layer_raw_u32", "record_tail_raw_u32",
    ]
    rows = []
    for file in sorted(root.rglob("*.texinfo")):
        try:
            records = parse_texinfo(file.read_bytes())
            for rec in records:
                name = rec["name"]
                m = ITEM_NAME.match(name)
                family = "item" if m else name.split("_", 1)[0]
                rows.append([
                    file.as_posix(), name, family, m.group(1) if m else "",
                    "NAME_ONLY_UNLINKED", rec["record_index"], rec["record_count"],
                    *(f"{rec[field]:.9g}" for field in ("u0", "v0", "u1", "v1")),
                    rec["uv_status"], rec["texture_layer_raw_u32"],
                    rec["record_tail_raw_u32"],
                ])
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            rows.append([file.as_posix(), "", "", "", f"UNPARSED: {exc}",
                         "", "", "", "", "", "", "", "", ""])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)
    return len(rows)


def run(paths: list[Path], dest: Path, layouts: list[str]) -> list[list[str]]:
    outdir = dest / "Textures" / "Previews"
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in paths:
        try:
            platform, textures = parse_g1t(path.read_bytes())
        except (OSError, ValueError) as e:
            rows.append([str(path), "", "", "", "", "", "", "", "", "FAILED_HEADER", str(e)])
            continue
        for i, tex in enumerate(textures):
            fmt, w, h = tex["format"], tex["width"], tex["height"]
            if fmt not in (0x66, 0x5f, 0x62, 0x5b, 0x08, 0x12):
                rows.append([str(path), i, "", hex(platform), hex(fmt), w, h, "", "", "UNSUPPORTED_FORMAT", "Only BC7/BC3 supported"])
                continue
            for layout in layouts:
                try:
                    png = decode_png(tex["payload"], w, h, layout, fmt)
                    name = f"{path.stem}__tex{i:02d}__{layout}.png"
                    outfile = outdir / name
                    outfile.write_bytes(png)
                    rows.append([str(path), i, layout, hex(platform), hex(fmt), w, h,
                                 outfile.as_posix(), hashlib.sha256(png).hexdigest(),
                                 "DECODED_UNVERIFIED", "Image validity and TEXINFO link not verified"])
                except (OSError, ValueError, SyntaxError) as e:
                    rows.append([str(path), i, layout, hex(platform), hex(fmt), w, h, "", "", "DECODE_FAILED", str(e)])
    report = dest / "Textures" / "texture_manifest.csv"
    with report.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(FIELDS)
        writer.writerows(rows)
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, action="append", required=True, help="G1T file or directory (repeatable)")
    p.add_argument("--dest", type=Path, default=Path("UnPack/2.0.1/Resources"))
    p.add_argument("--texinfo-root", type=Path, help="scan TEXINFO names recursively")
    p.add_argument("--layouts", default="linear,gob1,gob2", help="comma-separated layout candidates")
    p.add_argument("--max-files", type=int, default=10, help="safety cap; 0 means unlimited")
    args = p.parse_args()
    paths = sorted(set(f for src in args.input for f in ([src] if src.is_file() else src.rglob("*.g1t"))))
    if args.max_files:
        paths = paths[:args.max_files]
    layouts = [s.strip() for s in args.layouts.split(",") if s.strip()]
    if not layouts or any(s not in {"linear", "gob1", "gob2", "gob4", "gob8", "gob16", "gob32", "morton", "morton_yx", "morton8", "morton8_yx", "morton16", "morton16_yx", "morton32", "morton32_yx"} for s in layouts):
        p.error("invalid --layouts")
    if args.texinfo_root:
        n = texinfo_index(args.texinfo_root, args.dest / "Textures" / "texinfo_names.csv")
        print(f"TEXINFO indexed: {n}")
    rows = run(paths, args.dest, layouts)
    from collections import Counter
    print(f"G1T files: {len(paths)}; candidate results: {dict(Counter(row[9] for row in rows))}")


if __name__ == "__main__":
    main()
