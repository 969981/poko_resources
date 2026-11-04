#!/usr/bin/env python3
"""Export all 272 item sprites from the native 2.0.1 MountPoint_2 BC7 atlas.

Physical source and TEXINFO/UV names are validated. GOB16 was selected after
9 distributed comparisons with independent PokoHex PNGs. A score is only a
heuristic: output stays in Extra272Candidates; overlapping IDs are NOT overwritten.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from statistics import median
from PIL import Image

from Scripts.resources.g1t_to_png import decode_png, parse_g1t, parse_texinfo
from Scripts.resources.crop_native_item_atlas import crop_uv
from Scripts.resources.score_atlas_candidates import distance

COLUMNS = [
    "item_id", "sprite_name", "source_pack", "g1t_hash", "texinfo_hash",
    "g1t_path", "texinfo_path", "texinfo_record_index", "layer",
    "uv_u0", "uv_v0", "uv_u1", "uv_v1", "crop_box", "png", "png_sha256",
    "reference_png", "reference_distance", "overlaps_primary_atlas", "status"
]

def main():
    root = Path("UnPack/2.0.1/Resources")
    pack = Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/MountPoint_2/0x0017d6e2.fdata/native")
    g1t = pack / "root_009286_26a15463.g1t"
    texinfo = pack / "root_019254_51087a18.texinfo"
    refs = root / "Items/Icons"
    primary = root / "Items/Native_2.0.1/Icons"
    out = root / "Items/Native_2.0.1/Extra272Candidates"
    out.mkdir(parents=True, exist_ok=True)
    info = parse_texinfo(texinfo.read_bytes())
    platform, textures = parse_g1t(g1t.read_bytes())
    if len(info) != 272 or len(textures) != 1 or platform != 0x18:
        raise ValueError(f"unexpected source structures: {len(info)} sprites, {len(textures)} textures, {platform:#x}")
    tex = textures[0]
    if (tex["width"], tex["height"], tex["format"]) != (2048, 1024, 0x66):
        raise ValueError(f"unexpected source texture: {tex['width']} x {tex['height']}, {tex['format']:#x}")
    with Image.open(io.BytesIO(decode_png(tex["payload"], 2048, 1024, "gob16", 0x66))) as img:
        surface = img.convert("RGBA")

    rows, scores, overlap_ids, ids = [], [], [], set()
    for rec in info:
        if not rec["name"].startswith("item_"):
            raise ValueError(f"unexpected sprite name {rec['name']}")
        item_id = int(rec["name"].split("_")[1])
        if rec["name"] != f"item_{item_id:04d}":
            raise ValueError(f"unexpected sprite name {rec['name']}")
        if item_id in ids:
            raise ValueError(f"duplicate item {item_id} in 272 atlas")
        ids.add(item_id)
        if rec["texture_layer_raw_u32"] != 0 or rec["uv_status"] != "RECT_OK":
            raise ValueError(f"bad layer or UV at item {item_id}")
        uv = {f"uv_{key}": str(rec[key]) for key in ("u0", "v0", "u1", "v1")}
        icon, crop_box = crop_uv(surface, uv)
        if icon.size != (72, 72):
            raise ValueError(f"unexpected crop {item_id}: {icon.size}")
        filename = f"item_{item_id:04d}.png"
        dest = out / filename
        icon.save(dest, format="PNG")
        ref = refs / filename
        score = distance(dest, ref) if ref.is_file() else None
        if score is not None:
            scores.append(score)
        overlap = (primary / filename).exists()
        if overlap:
            overlap_ids.append(item_id)
        if score is None:
            status = "SOURCE_CROP_NO_REFERENCE"
        elif score >= 0.15:
            status = "SOURCE_CROP_REVIEW"
        else:
            status = "SOURCE_CROP_SIMILAR_REFERENCE"
        rows.append({
            "item_id": item_id, "sprite_name": rec["name"],
            "source_pack": "MountPoint_2/0x0017d6e2.fdata",
            "g1t_hash": "26a15463", "texinfo_hash": "51087a18",
            "g1t_path": g1t.as_posix(), "texinfo_path": texinfo.as_posix(),
            "texinfo_record_index": rec["record_index"], "layer": 0,
            **{f"uv_{k}": str(rec[k]) for k in ("u0", "v0", "u1", "v1")},
            "crop_box": str(crop_box), "png": dest.as_posix(),
            "png_sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
            "reference_png": ref.as_posix() if ref.is_file() else "",
            "reference_distance": "" if score is None else score,
            "overlaps_primary_atlas": str(overlap), "status": status,
        })
    if len(ids) != 272 or len(rows) != 272:
        raise ValueError("missing source icons")
    with (out / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    summary = {
        "source_g1t": g1t.as_posix(), "source_texinfo": texinfo.as_posix(),
        "g1t_format": "BC7 0x66", "layout": "gob16", "orientation": "top-v",
        "texture_size": [2048, 1024],
        "native_texinfo_records": 272, "png_count": len(rows),
        "icon_size": [72, 72], "reference_count": len(scores),
        "median_reference_distance": median(scores) if scores else None,
        "worst_reference_distance": max(scores) if scores else None,
        "reference_scores_are_heuristic": True,
        "overlap_with_primary_atlas_count": len(overlap_ids),
        "overlap_ids": sorted(overlap_ids), "distinct_additional_ids": len(ids) - len(overlap_ids),
        "status_counts": dict(Counter(r["status"] for r in rows)),
        "warning": "Reference similarity is not pixel identity. All PNGs stay separate from previous 1333 icons; overlapping IDs are not overwritten."
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
