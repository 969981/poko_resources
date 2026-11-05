#!/usr/bin/env python3
"""Source-validated Pokopia 2.0.1 non-item/non-Pokemon UI/material preview export.

One script has both a --plan mode for sparse GitHub checkout and a --run mode
that reads actual original TEXINFO/G1T bytes, checks record name, UV, layer,
hash-filename linkage and emits source-qualified Ounce PNG candidates.
Do not mistake filename-driven categories for item/material types.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw
from Scripts.resources.g1t_to_png import decode_png, parse_g1t, parse_texinfo
from Scripts.resources.crop_native_item_atlas import crop_uv

ROOT=Path("UnPack/2.0.1/Resources")
INDEX=ROOT/"Textures/Indexes/native_misc_texture_index.csv"
DEST=ROOT/"Textures/MiscNativeSamples"
FIELDS=[
    "texture_name","category_candidate","texinfo_hash","g1t_hash",
    "texinfo_path","g1t_path","record_index","layer","original_format",
    "canvas_width","canvas_height","layout","crop_box","crop_width","crop_height",
    "png_path","png_sha256","g1t_sha256","opaque_pixels","status","reason"
]


def read_index(path=INDEX):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def plan_candidates(rows, per_category=7):
    if per_category < 1 or per_category > 40:
        raise ValueError("per-category sample limit must be 1..40")
    selected=[]
    used=set()
    categories=("material_name_candidate","ui_icon_name_candidate",
                "ui_gameplay_name_candidate","other_native_sprite_name")
    for category in categories:
        matches=sorted((row for row in rows if row["category_candidate"]==category
                        and row["status"]=="INDEXED_ORIGINAL_TEXINFO_G1T_PAIR"
                        and row["texinfo_path"] and row["g1t_path"]),
                       key=lambda r:(r["g1t_hash"],r["texture_name"]))
        if not matches:
            continue
        # Spread across the original source hash space, avoiding same exact G1T
        # in the preview whenever independent G1T textures are available.
        indices=[round(j*(len(matches)-1)/max(1,per_category-1))
                 for j in range(min(per_category,len(matches)))]
        for i in indices:
            row=matches[i]
            key=(row["texinfo_hash"],row["g1t_hash"],row["record_index"])
            if key not in used:
                selected.append(row)
                used.add(key)
    return selected


def layout_for_texture(h,fmt):
    if fmt in (0x66,0x5f,0x62,0x5b,0x08,0x12):
        rows=(h+3)//4
    elif fmt==0x0a:
        rows=h
    else:
        raise ValueError(f"unknown native texture format {fmt:#x}")
    groups=max(1,rows//8)
    gob=min(16,1<<(groups.bit_length()-1))
    return f"ounce{gob}"


@lru_cache(maxsize=64)
def cached_texinfo(path):
    return parse_texinfo(Path(path).read_bytes())


@lru_cache(maxsize=4)
def cached_g1t(path):
    data=Path(path).read_bytes()
    platform,textures=parse_g1t(data)
    return hashlib.sha256(data).hexdigest(),platform,textures


@lru_cache(maxsize=4)
def cached_surface(path,layer,layout):
    _,_,textures=cached_g1t(path)
    tex=textures[layer]
    return decode_png(tex["payload"],tex["width"],tex["height"],layout,tex["format"])


def export(selected,outdir):
    outdir.mkdir(parents=True,exist_ok=True)
    records=[]
    for r in selected:
        row={c:"" for c in FIELDS}
        for key in ("texture_name","category_candidate","texinfo_hash",
                    "g1t_hash","texinfo_path","g1t_path"):
            row[key]=r[key]
        row["record_index"]=r["record_index"]
        row["layer"]=r["layer"]
        row["status"]="NOT_DECODED"
        try:
            tif=Path(r["texinfo_path"])
            gtf=Path(r["g1t_path"])
            if tif.stem.rsplit("_",1)[-1].lower()!=r["texinfo_hash"]:
                raise ValueError("original TEXINFO filename/hash mismatch")
            if gtf.stem.rsplit("_",1)[-1].lower()!=r["g1t_hash"]:
                raise ValueError("original G1T filename/hash mismatch")
            texinfos=cached_texinfo(str(tif))
            rec=texinfos[int(r["record_index"])]
            if rec["name"]!=r["texture_name"] or rec["uv_status"]!="RECT_OK":
                raise ValueError("native TEXINFO sprite name or rectangular UV mismatch")
            if rec["texture_layer_raw_u32"]!=int(r["layer"]):
                raise ValueError("native TEXINFO layer mismatch")
            if any(abs(rec[k]-float(r[f"uv_{k}"]))>0.000002 for k in
                   ("u0","v0","u1","v1")):
                raise ValueError("original UV differs from indexed TEXINFO record")
            digest,platform,textures=cached_g1t(str(gtf))
            row["g1t_sha256"]=digest
            if platform!=0x18:
                raise ValueError(f"expected Switch2 platform 0x18, got {platform:#x}")
            layer=int(r["layer"])
            if layer<0 or layer>=len(textures):
                raise ValueError("native TEXINFO layer outside G1T entries")
            tex=textures[layer]
            fmt,w,h=tex["format"],tex["width"],tex["height"]
            row.update(original_format=f"{fmt:#x}",canvas_width=str(w),canvas_height=str(h))
            layout=layout_for_texture(h,fmt)
            row["layout"]=layout
            data=cached_surface(str(gtf),layer,layout)
            with Image.open(io.BytesIO(data)) as im:
                crop,rect=crop_uv(im.convert("RGBA"),
                                   {f"uv_{k}":str(rec[k]) for k in ("u0","v0","u1","v1")})
            if min(crop.size)<1 or max(crop.size)>2048:
                raise ValueError(f"invalid native crop dimensions {crop.size}")
            name=re.sub(r"[^a-zA-Z0-9_-]","_",r["texture_name"])
            target=outdir/"Images"/(f"{name}__{r['texinfo_hash']}__{r['g1t_hash']}"
                                     f"__r{r['record_index']}.png")
            target.parent.mkdir(parents=True,exist_ok=True)
            crop.save(target,"PNG")
            with Image.open(target) as im:
                im.verify()
            alpha=crop.getchannel("A")
            n=sum(v>0 for v in alpha.getdata())
            row.update(crop_box=str(rect),crop_width=str(crop.width),crop_height=str(crop.height),
                       png_path=target.as_posix(),
                       png_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                       opaque_pixels=str(n),
                       status="PNG_CANDIDATE_UNVERIFIED" if n else "TRANSPARENT_CANDIDATE_REVIEW")
        except (ValueError,OSError,SyntaxError,KeyError,IndexError) as exc:
            row.update(status="SOURCE_OR_DECODE_FAILED",reason=str(exc))
        records.append(row)

    manifest=outdir/"misc_native_sample_manifest.csv"
    with manifest.open("w",encoding="utf-8",newline="") as f:
        wr=csv.DictWriter(f,fieldnames=FIELDS)
        wr.writeheader();wr.writerows(records)
    good=[r for r in records if r["png_path"]]
    if good:
        cw,ch,columns=185,205,5
        rows=(len(good)+columns-1)//columns
        sheet=Image.new("RGB",(columns*cw,rows*ch),(241,241,241))
        pen=ImageDraw.Draw(sheet)
        for i,r in enumerate(good):
            x,y=(i%columns)*cw,(i//columns)*ch
            with Image.open(r["png_path"]) as im:
                pic=im.convert("RGBA")
            pic.thumbnail((160,164),Image.Resampling.LANCZOS)
            box=Image.new("RGBA",pic.size,(255,255,255,255))
            box.alpha_composite(pic)
            sheet.paste(box.convert("RGB"),(x+(cw-pic.width)//2,y))
            pen.text((x+3,y+167),r["texture_name"][:26],fill=(20,20,20))
            pen.text((x+3,y+183),r["layout"]+" "+r["g1t_hash"],fill=(50,50,50))
        sheet.save(outdir/"contact_sheet_misc_native.png","PNG")
    summary={
        "source_samples":len(records),"native_decoded_pngs":len(good),
        "statuses":dict(Counter(r["status"] for r in records)),
        "by_candidate_category":dict(Counter(r["category_candidate"] for r in records)),
        "source_evidence":"Actual 2.0.1 G1T/TEXINFO bytes, layout index edge, UV crop, G1T and PNG SHA256",
        "warning":"Ounce decoded PNG CANDIDATES; category by filename only, scene rendering/gametype/identity not verified."
    }
    (outdir/"misc_native_sample_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return summary


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=Path,default=INDEX)
    p.add_argument("--out",type=Path,default=DEST)
    p.add_argument("--per-category",type=int,default=7)
    p.add_argument("--plan",type=Path,help="write exact selected source rows to JSON without opening native binaries")
    p.add_argument("--read-plan",type=Path,help="read previously selected JSON, then decode originals")
    args=p.parse_args()
    if args.plan:
        original=read_index(args.index)
        subset=plan_candidates(original,args.per_category)
        if not subset: raise ValueError("No native sprites with linked G1T found")
        args.plan.write_text(json.dumps(subset,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
        print(json.dumps({"sample_count":len(subset),
                          "source_paths":sorted(set(p for r in subset
                                for p in (r["g1t_path"],r["texinfo_path"])))},
                         ensure_ascii=False))
        return
    selected=json.loads(args.read_plan.read_text(encoding="utf-8")) if args.read_plan else plan_candidates(read_index(args.index),args.per_category)
    summary=export(selected,args.out)
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    if summary["native_decoded_pngs"] == 0:
        raise ValueError("No original native UI/material sprites decoded: inspect sample failures")


if __name__=="__main__":
    main()
