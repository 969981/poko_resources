#!/usr/bin/env python3
"""M5 exploratory Pokopia G1T -> BC7 PNG previews and TEXINFO name index.

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


def decode_png(payload: bytes, width: int, height: int, layout: str) -> bytes:
    if layout == "linear":
        linear = payload
    elif layout.startswith("gob"):
        linear = unswizzle_gob_bc7(payload, width, height, int(layout[3:]))
    else:
        raise ValueError(f"unsupported layout {layout}")
    with Image.open(io.BytesIO(make_bc7_dds(linear, width, height))) as image:
        image.load()
        if image.size != (width, height):
            raise ValueError("decoded image dimensions do not match")
        out = io.BytesIO()
        image.convert("RGBA").save(out, format="PNG")
        return out.getvalue()


def texinfo_index(root: Path, output: Path) -> int:
    rows = []
    for file in sorted(root.rglob("*.texinfo")):
        try:
            data = file.read_bytes()
            if len(data) < 8 or u32(data, 0) != 1:
                raise ValueError("unexpected TEXINFO header")
            name = data[4:68].split(b"\x00", 1)[0].decode("ascii")
            if not TEXINFO_NAME.fullmatch(name):
                raise ValueError("invalid TEXINFO name")
            m = ITEM_NAME.match(name)
            family = "item" if m else name.split("_", 1)[0]
            rows.append([file.as_posix(), name, family, m.group(1) if m else "", "NAME_ONLY_UNLINKED"])
        except (ValueError, UnicodeDecodeError) as e:
            rows.append([file.as_posix(), "", "", "", f"UNPARSED: {e}"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["texinfo_path", "texture_name", "family", "item_id_candidate", "link_status"])
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
            if fmt not in (0x66, 0x5f):
                rows.append([str(path), i, "", hex(platform), hex(fmt), w, h, "", "", "UNSUPPORTED_FORMAT", "Only BC7 supported"])
                continue
            for layout in layouts:
                try:
                    png = decode_png(tex["payload"], w, h, layout)
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
    if not layouts or any(s not in {"linear", "gob1", "gob2", "gob4", "gob8", "gob16", "gob32"} for s in layouts):
        p.error("invalid --layouts")
    if args.texinfo_root:
        n = texinfo_index(args.texinfo_root, args.dest / "Textures" / "texinfo_names.csv")
        print(f"TEXINFO indexed: {n}")
    rows = run(paths, args.dest, layouts)
    from collections import Counter
    print(f"G1T files: {len(paths)}; candidate results: {dict(Counter(row[9] for row in rows))}")


if __name__ == "__main__":
    main()
