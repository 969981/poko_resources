#!/usr/bin/env python3
"""M5: export ALL 1,333 source-linked native two-layer item atlas sprites.

Unlike exploratory previews, this job fixes the empirically verified layout
candidate (Ounce/0x18 GOB height 16, top V origin). It always preserves source evidence,
keeps PokoHex references untouched, and reports discrepancies. Distinct
reference PNGs are NOT treated as proof of identical native pixels.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path
from statistics import median

from PIL import Image

from Scripts.resources.crop_native_item_atlas import crop_uv
from Scripts.resources.g1t_to_png import decode_png, parse_g1t, parse_texinfo
from Scripts.resources.score_atlas_candidates import distance

FIELDS = ["item_id", "sprite_name", "layer", "record_index", "g1t_path",
          "texinfo_path", "uv_u0", "uv_v0", "uv_u1", "uv_v1",
          "crop_box", "image_width", "image_height", "png_path",
          "png_sha256", "reference_png", "reference_distance", "status"]


def native_reference(a, b):
    # Both are source texture resources; no inferred SHA equivalence.
    return str(a), str(b)


def export(g1t: Path, texinfo: Path, uv_manifest: Path, references: Path,
           outdir: Path) -> dict:
    atlas = parse_texinfo(texinfo.read_bytes())
    with uv_manifest.open(encoding="utf-8-sig", newline="") as f:
        indexed = list(csv.DictReader(f))
    if len(indexed) != 1333 or len(atlas) != len(indexed):
        raise ValueError(f"source atlas must contain 1,333 records, found {len(atlas)} / {len(indexed)}")

    by_id, selected = {}, {}
    for r in indexed:
        i = int(r["item_id"])
        if i in by_id:
            raise ValueError(f"duplicate native atlas item {i}")
        by_id[i] = r
        rec_idx = int(r["record_index"])
        original = atlas[rec_idx]
        if original["name"] != r["sprite_name"]:
            raise ValueError(f"TEXINFO record name differs from index: {i}")
        if original["texture_layer_raw_u32"] != int(r["texture_layer_raw_u32"]):
            raise ValueError(f"TEXINFO layer mismatch for item {i}")
        if not r["status"].startswith("INDEX_EDGE_AND_NATIVE_TEXINFO_UV"):
            raise ValueError(f"no native texture index evidence for item {i}")
        if any(abs(original[key] - float(r[col])) > 2e-6 for key, col in
               [("u0","uv_u0"),("v0","uv_v0"),("u1","uv_u1"),("v1","uv_v1")]):
            raise ValueError(f"UV coordinates changed for {i}")
        selected[i] = original

    platform, tex = parse_g1t(g1t.read_bytes())
    if platform != 0x18 or len(tex) != 2:
        raise ValueError(f"unexpected platform / G1T texture count: {platform:#x} / {len(tex)}")
    if [(t["width"], t["height"], t["format"]) for t in tex] != [(2048,2048,0x66)]*2:
        raise ValueError("unexpected G1T atlas dimensions or format")
    layers = []
    for t in tex:
        data = decode_png(t["payload"], t["width"], t["height"], "ounce16", t["format"])
        with Image.open(io.BytesIO(data)) as im:
            layers.append(im.convert("RGBA"))

    outdir.mkdir(parents=True, exist_ok=True)
    rows, scores, counts = [], [], Counter()
    for item_id in sorted(by_id):
        row, rec = by_id[item_id], selected[item_id]
        layer = int(rec["texture_layer_raw_u32"])
        crop, box = crop_uv(layers[layer], row)
        if crop.size != (72,72):
            raise ValueError(f"native icon {item_id} must be 72x72, got {crop.size}")
        filename = f"item_{item_id:04d}.png"
        target = outdir / filename
        crop.save(target, format="PNG")
        sha = hashlib.sha256(target.read_bytes()).hexdigest()
        ref = references / filename
        d = distance(target, ref) if ref.is_file() else None
        if d is None:
            status = "NATIVE_CROP_NO_REFERENCE"
        elif d <= 0.15:
            status = "NATIVE_CROP_REFERENCE_SIMILAR"
            scores.append(d)
        else:
            status = "NATIVE_CROP_REVIEW"
            scores.append(d)
        counts[status] += 1
        rows.append({
            "item_id": item_id, "sprite_name": row["sprite_name"],
            "layer": layer, "record_index": row["record_index"],
            "g1t_path": g1t.as_posix(), "texinfo_path": texinfo.as_posix(),
            **{c: row[c] for c in ("uv_u0","uv_v0","uv_u1","uv_v1")},
            "crop_box": str(box), "image_width": crop.width, "image_height": crop.height,
            "png_path": target.as_posix(), "png_sha256": sha,
            "reference_png": ref.as_posix() if ref.is_file() else "",
            "reference_distance": d if d is not None else "", "status": status
        })

    report_path = outdir.parent
    with (report_path / "native_icon_manifest.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "source_g1t": g1t.as_posix(),
        "source_texinfo": texinfo.as_posix(),
        "atlas_layers": 2,
        "atlas_dimensions_per_layer": [2048, 2048],
        "g1t_platform": "0x18",
        "g1t_format": "0x66 BC7",
        "layout": "ounce16",
        "v_origin": "top",
        "native_atlas_records": 1333,
        "generated_pngs": len(rows),
        "native_sizes": [72, 72],
        "reference_count": len(scores),
        "status_counts": dict(counts),
        "median_reference_distance": median(scores) if scores else None,
        "max_reference_distance": max(scores) if scores else None,
        "reference_threshold_is_heuristic": 0.15,
        "warning": "Native G1T and TEXINFO indices validated; a reference image can differ due to scaling, transparency or external asset conversion. Never overwrite Resources/Items/Icons."
    }
    (report_path / "native_icon_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    pack = Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native")
    root = Path("UnPack/2.0.1/Resources")
    parser.add_argument("--g1t", type=Path, default=pack / "root_038147_a0ce9914.g1t")
    parser.add_argument("--texinfo", type=Path, default=pack / "root_042753_b4b1fe49.texinfo")
    parser.add_argument("--uv", type=Path, default=root / "Textures/Indexes/item_atlas_1333_uv.csv")
    parser.add_argument("--refs", type=Path, default=root / "Items/Icons")
    parser.add_argument("--out", type=Path, default=root / "Items/Native_2.0.1/Icons")
    args = parser.parse_args()
    print(json.dumps(export(args.g1t, args.texinfo, args.uv, args.refs, args.out),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
