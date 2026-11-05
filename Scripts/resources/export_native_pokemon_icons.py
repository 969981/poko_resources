#!/usr/bin/env python3
"""Extract all 609 source-linked Pokopia 2.0.1 Pokémon icon TEXINFO records.

The manifest is one row per TEXINFO entry, not per creature species, and 6
names occur in different original resources. Include both texture hashes in
each PNG filename to preserve those native variants.

Every image is a source-derived PNG CANDIDATE; a successful G1T/BC7 decode
does not prove Pokédex identity, final UV/render fidelity, or screen similarity.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw

from Scripts.resources.g1t_to_png import decode_png, parse_g1t, parse_texinfo
from Scripts.resources.crop_native_item_atlas import crop_uv


ROOT = Path("UnPack/2.0.1/Resources/Pokemon")
INDEX = ROOT / "pokemon_texture_index.csv"
NATIVE = Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native")
DEST = ROOT / "NativeCandidates"
FIELDS = [
    "texture_name", "category", "texture_number_candidate",
    "texinfo_hash", "g1t_hash", "texinfo_file", "g1t_file",
    "source_kind", "texinfo_record_index", "texture_layer", "format",
    "g1t_width", "g1t_height", "swizzle_layout", "uv_rect",
    "crop_width", "crop_height", "opaque_pixels", "png_path",
    "png_sha256", "g1t_sha256", "source_evidence", "status", "reason"
]


@lru_cache(maxsize=16)
def get_g1t(path: str):
    blob = Path(path).read_bytes()
    if blob[:8] != b"GT1G0600":
        raise ValueError("not original GT1G0600")
    platform, textures = parse_g1t(blob)
    if platform != 0x18:
        raise ValueError(f"expected platform 0x18, got {platform:#x}")
    return hashlib.sha256(blob).hexdigest(), textures


@lru_cache(maxsize=64)
def get_texinfo(path: str):
    return parse_texinfo(Path(path).read_bytes())


def layout_for_bc7(height: int) -> str:
    # Empirically checked on 2048px item atlas, 256px Pokémon and 64px
    # Pokémon UNI icon samples. For block-linear BC7 the number of 8-row
    # GOBs is bounded by the compressed block-row count.
    block_rows = (height + 3) // 4
    n = max(1, block_rows // 8)
    height_gobs = min(16, 1 << (n.bit_length() - 1))
    return f"ounce{height_gobs}"


def draw_sheet(records, category: str, output: Path):
    valid = [r for r in records if r["category"] == category and r["png_path"]]
    # Distributed sample across the sorted source set to surface variation.
    picked = [valid[round(i * (len(valid) - 1) / 35)] for i in range(36)] if len(valid) >= 36 else valid
    cols, cell_w, cell_h = 6, 200, 185
    rows = (len(picked) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (241, 241, 241))
    pen = ImageDraw.Draw(sheet)
    for i, record in enumerate(picked):
        x, y = (i % cols) * cell_w, (i // cols) * cell_h
        with Image.open(record["png_path"]) as f:
            icon = f.convert("RGBA")
        max_dimension = max(icon.size)
        factor = min(3, max(1, 148 // max_dimension))
        icon = icon.resize((icon.width * factor, icon.height * factor), Image.Resampling.NEAREST)
        if icon.width > 148 or icon.height > 148:
            icon.thumbnail((148,148), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (icon.width,icon.height),(255,255,255,255))
        canvas.alpha_composite(icon)
        sheet.paste(canvas.convert("RGB"), (x + (cell_w-icon.width)//2,y+4))
        pen.text((x+5,y+155),record["texture_name"][:26],fill=(25,25,25))
        pen.text((x+5,y+171),record["swizzle_layout"]+" "+record["g1t_hash"],fill=(70,70,70))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output,"PNG")


def main() -> None:
    with INDEX.open(encoding="utf-8-sig", newline="") as f:
        original = list(csv.DictReader(f))
    if len(original) != 609:
        raise ValueError(f"expected 609 source entries, got {len(original)}")
    if Counter(r["category"] for r in original) != {"pokemon": 301, "pokemon_uni": 308}:
        raise ValueError("source category counts changed; re-audit first")

    DEST.mkdir(parents=True, exist_ok=True)
    results, files_seen, category_ok = [], set(), Counter()
    source_counts = Counter()
    for row in original:
        name = row["texture_name"]
        category = row["category"]
        report = {
            "texture_name": name, "category": category,
            "texture_number_candidate": row["texture_number_candidate"],
            "texinfo_hash": row["texinfo_hash"], "g1t_hash": row["g1t_hash"],
            "texinfo_file": row["texinfo_filename"], "g1t_file": row["g1t_filename"],
            "source_kind": row["native_source_kind"],
            "texinfo_record_index": row["texinfo_record_index"],
            "texture_layer": row["texture_layer"],
            "format": "", "g1t_width": "", "g1t_height": "",
            "swizzle_layout": "", "uv_rect": "",
            "crop_width": "", "crop_height": "", "opaque_pixels": "",
            "png_path": "", "png_sha256": "", "g1t_sha256": "",
            "source_evidence": "KIDSOBJDB_HASH_LINK_AND_ORIGINAL_TEXINFO_G1T",
            "status": "NOT_YET_DECODED", "reason": ""
        }
        try:
            if row["status"] != "PHYSICAL_G1T_PRESENT" or not row["g1t_filename"]:
                raise ValueError("no physical native G1T source in input index")
            if row["texinfo_hash"] not in row["texinfo_filename"] or row["g1t_hash"] not in row["g1t_filename"]:
                raise ValueError("index hash and original filename mismatch")
            texinfo = NATIVE / row["texinfo_filename"]
            g1t = NATIVE / row["g1t_filename"]
            if g1t.stat().st_size != int(row["g1t_file_size"]):
                raise ValueError("source G1T physical file size differs from index")
            info = get_texinfo(str(texinfo))
            rec_idx = int(row["texinfo_record_index"])
            if not (0 <= rec_idx < len(info)):
                raise ValueError("original TEXINFO index out of bounds")
            rec = info[rec_idx]
            if rec["name"] != name or rec["record_count"] != int(row["texinfo_record_count"]):
                raise ValueError("original TEXINFO name/count differs from index")
            if rec["uv_status"] != "RECT_OK":
                raise ValueError(f"nonrect original UV: {rec['uv_status']}")
            for orig, index_key in (("u0","atlas_u0"),("v0","atlas_v0"),
                                    ("u1","atlas_u1"),("v1","atlas_v1")):
                if abs(rec[orig]-float(row[index_key])) > 0.000002:
                    raise ValueError(f"original TEXINFO {orig} differs from index")
            layer_index = int(row["texture_layer"])
            if rec["texture_layer_raw_u32"] != layer_index:
                raise ValueError("original layer index differs from input index")
            g1t_sha, textures = get_g1t(str(g1t))
            if not (0 <= layer_index < len(textures)):
                raise ValueError(f"TEXINFO layer {layer_index} outside G1T texture entries {len(textures)}")
            texture = textures[layer_index]
            width,height,fmt = texture["width"],texture["height"],texture["format"]
            report.update(g1t_sha256=g1t_sha, format=hex(fmt),
                          g1t_width=width,g1t_height=height)
            if fmt != 0x66:
                raise ValueError(f"unsupported Pokémon candidate format {fmt:#x} (BC7 expected)")
            layout = layout_for_bc7(height)
            report["swizzle_layout"] = layout
            image = decode_png(texture["payload"],width,height,layout,fmt)
            with Image.open(io.BytesIO(image)) as decoded:
                crop,box = crop_uv(decoded.convert("RGBA"),
                                   {f"uv_{k}":str(rec[k]) for k in ("u0","v0","u1","v1")})
            if min(crop.size) < 1 or max(crop.size) > 1024:
                raise ValueError(f"suspicious UV crop size {crop.size}")
            target = DEST / category / f"{name}__{row['texinfo_hash']}__{row['g1t_hash']}.png"
            if target.name in files_seen:
                raise ValueError("collision in source-qualified PNG output names")
            files_seen.add(target.name)
            target.parent.mkdir(parents=True, exist_ok=True)
            crop.save(target, format="PNG")
            opaque = crop.getchannel("A").getbbox()
            px = sum(1 for value in crop.getchannel("A").getdata() if value > 0)
            report.update(
                uv_rect=str(box),crop_width=crop.width,crop_height=crop.height,
                opaque_pixels=px,png_path=target.as_posix(),
                png_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                status="PNG_CANDIDATE_UNVERIFIED" if opaque else "TRANSPARENT_CANDIDATE_REVIEW"
            )
            category_ok[category] += 1
            source_counts[row["native_source_kind"]] += 1
        except (ValueError, OSError, SyntaxError, KeyError) as exc:
            report.update(status="FAILED_SOURCE_OR_DECODE", reason=str(exc))
        results.append(report)

    with (DEST / "pokemon_native_manifest.csv").open("w",encoding="utf-8",newline="") as f:
        w = csv.DictWriter(f,fieldnames=FIELDS)
        w.writeheader();w.writerows(results)
    for cat in ("pokemon","pokemon_uni"):
        draw_sheet(results,cat,DEST / f"contact_sheet_{cat}.png")
    summary = {
        "game_version": "2.0.1", "source_rows": len(original),
        "name_distinct": len(set(r["texture_name"] for r in original)),
        "category_rows": dict(Counter(r["category"] for r in original)),
        "native_png_candidates": sum(bool(r["png_path"]) for r in results),
        "statuses": dict(Counter(r["status"] for r in results)),
        "candidate_by_category": dict(category_ok),
        "source_recovery_kinds":dict(source_counts),
        "expected_standalone_native_texture_hashes":603,
        "duplicate_names_are_kept_by_texinfo_and_g1t_hash": True,
        "layout_selection_rule": "BC7 platform 0x18 Ounce GOB permutation; tested against native item references and 64/256px pokemon; GOB height based on BC block rows",
        "warning": "All outputs are original-source PNG CANDIDATES, not independently proven game-visible pixel-perfect icons or species IDs."
    }
    (DEST / "pokemon_native_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__ == "__main__":
    main()
