#!/usr/bin/env python3
"""Decode both layers of a native G1T atlas and crop TEXINFO item regions.

All images are CANDIDATE previews. Layout/orientation/visual fidelity remain
unverified; this never overwrites Resources/Items/Icons.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image

from Scripts.resources.g1t_to_png import decode_png, parse_g1t

COLUMNS = [
    "item_id", "sprite_name", "layer", "layout", "crop_box", "png_path",
    "sha256", "status", "reason",
]


def split_bc_layers(payload: bytes, width: int, height: int, layer_count: int) -> list[bytes]:
    """Require exact, unambiguous BC3/BC7 layer boundaries; no silent mip guessing."""
    if layer_count < 1:
        raise ValueError("invalid layer count")
    bytes_per_layer = ((width + 3) // 4) * ((height + 3) // 4) * 16
    if len(payload) != bytes_per_layer * layer_count:
        raise ValueError(
            f"payload {len(payload)} bytes does not equal {layer_count} "
            f"layers x {bytes_per_layer} bytes; mip/array layout needs research"
        )
    return [
        payload[n * bytes_per_layer:(n + 1) * bytes_per_layer]
        for n in range(layer_count)
    ]


def crop_uv(image: Image.Image, entry: dict[str, str], *, flip_v: bool = False) -> tuple[Image.Image, tuple[int, int, int, int]]:
    w, h = image.size
    u0, v0, u1, v1 = (float(entry[k]) for k in
                      ("uv_u0", "uv_v0", "uv_u1", "uv_v1"))
    if not all(math.isfinite(x) for x in (u0, v0, u1, v1)):
        raise ValueError("nonfinite UV")
    if not (0 <= u0 < u1 <= 1.00001 and 0 <= v0 < v1 <= 1.00001):
        raise ValueError("invalid UV rectangle")
    if flip_v:
        v0, v1 = 1 - v1, 1 - v0
    rect = (round(u0 * w), round(v0 * h), round(u1 * w), round(v1 * h))
    if not (0 <= rect[0] < rect[2] <= w and
            0 <= rect[1] < rect[3] <= h):
        raise ValueError("UV cropped outside image")
    return image.crop(rect), rect


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g1t", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path(
        "UnPack/2.0.1/Resources/Textures/Indexes/item_atlas_1333_uv.csv"
    ))
    parser.add_argument("--out", type=Path, default=Path(
        "UnPack/2.0.1/Resources/Textures/AtlasCandidates"
    ))
    parser.add_argument("--layouts", default="linear,gob1,gob2,gob4,gob8")
    parser.add_argument("--ids", default="6,7,8,1677,1764,1765,2742",
                        help="comma-separated item IDs; samples by default")
    parser.add_argument("--flip-v", action="store_true",
                        help="interpret TEXINFO v=0 as image bottom instead of top")
    args = parser.parse_args()

    with args.manifest.open(encoding="utf-8-sig", newline="") as fp:
        original = list(csv.DictReader(fp))
    selected = {int(s.strip()) for s in args.ids.split(",") if s.strip()}
    entries = [r for r in original if int(r["item_id"]) in selected]
    if not entries or any(r["status"].split("__")[0] != "INDEX_EDGE_AND_NATIVE_TEXINFO_UV"
                          for r in entries):
        raise ValueError("no verified metadata references for selected atlas entries")
    required_layers = max(int(e["texture_layer_raw_u32"]) for e in original) + 1
    if required_layers != 2:
        raise ValueError(f"expected two atlas layers in current 2.0.1 manifest, got {required_layers}")

    platform, textures = parse_g1t(args.g1t.read_bytes())
    if len(textures) != 1:
        raise ValueError(f"atlas G1T has {len(textures)} texture entries, not one")
    tex = textures[0]
    if tex["format"] not in (0x66, 0x5f, 0x62, 0x5b, 0x08, 0x12):
        raise ValueError(f"unknown atlas format: {tex['format']:#x}")
    layers = split_bc_layers(tex["payload"], tex["width"], tex["height"], required_layers)
    layouts = [s.strip() for s in args.layouts.split(",") if s.strip()]
    if any(s not in ("linear", "gob1", "gob2", "gob4", "gob8", "gob16", "gob32")
           for s in layouts):
        raise ValueError("unsupported layout candidate")

    args.out.mkdir(parents=True, exist_ok=True)
    rows = []
    for layout in layouts:
        for layer, binary in enumerate(layers):
            relevant = [e for e in entries if int(e["texture_layer_raw_u32"]) == layer]
            if not relevant:
                continue
            try:
                decoded = decode_png(binary, tex["width"], tex["height"], layout, tex["format"])
                with Image.open(io.BytesIO(decoded)) as decoded_img:
                    canvas = decoded_img.convert("RGBA")
                for e in relevant:
                    try:
                        crop, rectangle = crop_uv(canvas, e, flip_v=args.flip_v)
                        filename = f"item_{int(e['item_id']):04d}__layer{layer}__{layout}"
                        if args.flip_v:
                            filename += "__flipped_v"
                        output = args.out / (filename + ".png")
                        crop.save(output, format="PNG")
                        sha = hashlib.sha256(output.read_bytes()).hexdigest()
                        rows.append([e["item_id"], e["sprite_name"], layer, layout,
                                     str(rectangle), output.as_posix(), sha,
                                     "CROPPED_UNVERIFIED", "Visual comparison needed"])
                    except (OSError, ValueError) as exc:
                        rows.append([e["item_id"], e["sprite_name"], layer, layout,
                                     "", "", "", "CROP_FAILED", str(exc)])
            except (OSError, ValueError, SyntaxError) as exc:
                for e in relevant:
                    rows.append([e["item_id"], e["sprite_name"], layer, layout,
                                 "", "", "", "LAYOUT_DECODE_FAILED", str(exc)])
    with (args.out / "atlas_candidate_manifest.csv").open("w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(json.dumps({
        "format": hex(tex["format"]), "platform": hex(platform),
        "dimensions_per_layer": [tex["width"], tex["height"]],
        "layers": len(layers), "selected_items": len(entries),
        "statuses": {s: sum(r[7] == s for r in rows) for s in
                     sorted({r[7] for r in rows})},
        "note": "Decoded image and per-item crops are candidates, not native-verified final icons",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
