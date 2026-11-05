#!/usr/bin/env python3
"""M5 exploratory second item atlas (272 native TEXINFO records, one G1T)."""
from __future__ import annotations
import argparse
import csv
import io
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from PIL import Image
from Scripts.resources.g1t_to_png import parse_g1t, parse_texinfo, decode_png
from Scripts.resources.crop_native_item_atlas import crop_uv
from Scripts.resources.score_atlas_candidates import distance


def main():
    p=argparse.ArgumentParser(description=__doc__)
    base=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/MountPoint_2/0x0017d6e2.fdata/native")
    p.add_argument("--g1t",type=Path,default=base/"root_009286_26a15463.g1t")
    p.add_argument("--texinfo",type=Path,default=base/"root_019254_51087a18.texinfo")
    p.add_argument("--refs",type=Path,default=Path("UnPack/2.0.1/Resources/Items/Icons"))
    p.add_argument("--out",type=Path,default=Path("atlas272-preview"))
    args=p.parse_args()
    sprites=parse_texinfo(args.texinfo.read_bytes())
    platform,tex=parse_g1t(args.g1t.read_bytes())
    if len(sprites)!=272 or len(tex)!=1 or platform!=0x18:
        raise ValueError(f"bad atlas metadata: {len(sprites)}, {len(tex)}, {platform:#x}")
    t=tex[0]
    if (t["width"],t["height"],t["format"])!=(2048,1024,0x66):
        raise ValueError(f"unexpected G1T header: {t['width']} x {t['height']} fmt={t['format']:#x}")
    if any(r["texture_layer_raw_u32"]!=0 for r in sprites):
        raise ValueError("non-zero TEXINFO layer")
    indices=sorted(set([0,1,15,53,98,137,186,230,271]))
    selected=[sprites[i] for i in indices]
    args.out.mkdir(parents=True,exist_ok=True)
    layouts=["linear","gob1","gob2","gob4","gob8","gob16","gob32","ounce16","morton8","morton16","morton16_yx"]
    records=[]
    for layout in layouts:
        try:
            png=decode_png(t["payload"],t["width"],t["height"],layout,t["format"])
            with Image.open(io.BytesIO(png)) as im: atlas=im.convert("RGBA")
        except Exception as e:
            records.append({"item_id":"","layout":layout,"score":"","png":"","status":"FAILED","reason":str(e)})
            continue
        for rec in selected:
            name=rec["name"]
            id=int(name.split("_")[1])
            uv={f"uv_{k}":str(rec[k]) for k in ("u0","v0","u1","v1")}
            crop,box=crop_uv(atlas,uv)
            if crop.size!=(72,72):
                raise ValueError(f"{name} unexpected crop {crop.size}")
            dest=args.out/f"{name}__{layout}.png"
            crop.save(dest)
            ref=args.refs/f"item_{id:04d}.png"
            d=distance(dest,ref) if ref.exists() else None
            records.append({"item_id":id,"layout":layout,"score":"" if d is None else d,
                            "png":dest.as_posix(),"status":"UNVERIFIED_CANDIDATE","reason":""})
    with (args.out/"candidate_manifest.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["item_id","layout","score","png","status","reason"])
        writer.writeheader();writer.writerows(records)
    grouped=defaultdict(list)
    for r in records:
        if r["score"]!="":grouped[r["layout"]].append(r["score"])
    score=sorted([{"layout":k,"count":len(v),"median_difference":round(median(v),8),
                   "worst_difference":round(max(v),8)} for k,v in grouped.items()],
                 key=lambda x:x["median_difference"])
    report={"g1t":args.g1t.as_posix(),"texinfo":args.texinfo.as_posix(),
            "source_count":len(sprites),"samples":[int(r["name"].split("_")[1]) for r in selected],
            "pixel_dimensions":[t["width"],t["height"]],"format":"BC7","rankings":score,
            "warning":"This is a layout comparison only, not a signed-off batch export."}
    (args.out/"summary.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
