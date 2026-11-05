#!/usr/bin/env python3
"""M5 first real Pokémon icon decoding batch for Pokopia 2.0.1 RomFS.

Reads confirmed TEXINFO->G1T hash relationships and real G1T bytes.
Generates candidate PNGs and a labeled contact sheet for visual inspection.
Names beginning icon_poke_ are texture names, NOT independently proven
Pokédex numbers. No candidate is treated as final before visual validation.
"""
from __future__ import annotations
import csv
import io
import json
from collections import Counter, defaultdict
from pathlib import Path
from PIL import Image, ImageDraw
from Scripts.resources.g1t_to_png import parse_g1t, parse_texinfo, decode_png
from Scripts.resources.crop_native_item_atlas import crop_uv

ROOT = Path("UnPack/2.0.1/Resources/Pokemon")
NATIVE = Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native")
LAYOUTS = ["linear", "gob1", "gob2", "gob4", "gob8", "gob16",
           "morton", "morton_yx", "morton8", "morton8_yx", "morton16", "morton16_yx", "ounce2", "ounce8"]
FIELDS = ["texture_name", "category", "texinfo_hash", "g1t_hash", "g1t_file",
          "layer", "format", "width", "height", "layout", "png",
          "crop_width", "crop_height", "status", "reason"]


def read_index():
    with (ROOT / "pokemon_sample_manifest.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def main():
    source = read_index()
    if len(source) != 16 or sum(row["category"]=="pokemon" for row in source)!=8 or \
       sum(row["category"]=="pokemon_uni" for row in source)!=8:
        raise ValueError("unexpected Pokémon sample scope")
    folder = ROOT / "Previews"
    folder.mkdir(parents=True, exist_ok=True)
    report, photos, counts = [], {}, Counter()
    for row in source:
        if row["status"] != "PHYSICAL_G1T_PRESENT":
            raise ValueError(f"sample source missing: {row['texture_name']}")
        name = row["texture_name"]
        g1t = NATIVE / row["g1t_filename"]
        texinfo = NATIVE / row["texinfo_filename"]
        if g1t.stat().st_size != int(row["g1t_file_size"]):
            raise ValueError(f"original G1T bytes mismatch for {name}")
        info = parse_texinfo(texinfo.read_bytes())
        rec = info[int(row["texinfo_record_index"])]
        if rec["name"] != name or rec["record_count"] != int(row["texinfo_record_count"]):
            raise ValueError(f"original TEXINFO identity mismatch: {name}")
        for field, source_field in (("u0","atlas_u0"),("v0","atlas_v0"),("u1","atlas_u1"),("v1","atlas_v1")):
            if abs(rec[field] - float(row[source_field])) > 2e-6:
                raise ValueError(f"original UV mismatch: {name}:{field}")
        platform, textures = parse_g1t(g1t.read_bytes())
        if platform != 0x18 or len(textures) <= rec["texture_layer_raw_u32"]:
            raise ValueError(f"unexpected platform/layers in G1T {name}")
        t = textures[rec["texture_layer_raw_u32"]]
        for layout in LAYOUTS:
            result = {
                "texture_name": name, "category": row["category"],
                "texinfo_hash": row["texinfo_hash"], "g1t_hash": row["g1t_hash"],
                "g1t_file": g1t.as_posix(), "layer": rec["texture_layer_raw_u32"],
                "format": hex(t["format"]), "width": t["width"], "height": t["height"],
                "layout": layout, "png": "", "crop_width": "", "crop_height": "",
                "status": "", "reason": ""
            }
            try:
                data = decode_png(t["payload"], t["width"], t["height"], layout, t["format"])
                with Image.open(io.BytesIO(data)) as im:
                    uv = {f"uv_{x}": str(rec[x]) for x in ("u0","v0","u1","v1")}
                    png, bbox = crop_uv(im.convert("RGBA"), uv)
                if max(png.size) > 1024 or min(png.size) < 1:
                    raise ValueError(f"invalid crop dimensions {png.size}")
                output = folder / f"{name}__{layout}.png"
                png.save(output, format="PNG")
                photos[(name,layout)] = png.copy()
                result.update(png=output.as_posix(),crop_width=png.width,
                              crop_height=png.height,status="UNVERIFIED_PNG_CANDIDATE")
            except (ValueError, OSError, SyntaxError) as exc:
                result.update(status="LAYOUT_NOT_DECODED", reason=str(exc))
            counts[result["status"]] += 1
            report.append(result)
    with (folder / "pokemon_sample_manifest.csv").open("w", encoding="utf-8", newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        w.writeheader();w.writerows(report)
    cell_w, cell_h, left = 172, 174, 185
    sheet = Image.new("RGB", (left + cell_w * len(LAYOUTS), (len(source)+1)*cell_h), (238,238,238))
    draw = ImageDraw.Draw(sheet)
    draw.text((4,8),"Pokopia native Pokemon G1T candidates",fill=(0,0,0))
    for x, layout in enumerate(LAYOUTS):
        draw.text((left + x*cell_w + 5, 20), layout, fill=(0,0,0))
    for i,row in enumerate(source):
        y=(i+1)*cell_h
        name=row["texture_name"]
        draw.text((4,y+15),name[:24],fill=(0,0,0))
        for x,layout in enumerate(LAYOUTS):
            key=(name,layout)
            if key not in photos:continue
            png=photos[key]
            scaled=png.resize((min(150,png.width*2),min(150,png.height*2)),Image.Resampling.NEAREST)
            px=left+x*cell_w+(cell_w-scaled.width)//2
            py=y+14
            background=Image.new("RGBA",scaled.size,(245,245,245,255))
            background.alpha_composite(scaled)
            sheet.paste(background.convert("RGB"),(px,py))
    sheet.save(folder / "pokemon_layout_contact_sheet.png", format="PNG")
    summary={
        "sample_count":len(source), "category_counts":dict(Counter(x["category"] for x in source)),
        "layouts":LAYOUTS, "results":dict(counts),
        "candidate_pngs":len(photos), "sheet":"pokemon_layout_contact_sheet.png",
        "warning":"These are native source candidate images, not pixel-verified sprites or confirmed Pokédex identities. Choose swizzle based on visual inspection and multiple examples before batch export."
    }
    (folder / "summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
