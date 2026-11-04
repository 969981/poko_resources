#!/usr/bin/env python3
"""M5 preview of secondary 14-icon atlas (BC7 layer 0 + raw BGRA layer 1).

Only writes candidate images and a score ledger, never final Icons or references.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

from PIL import Image
from Scripts.resources.g1t_to_png import decode_png, parse_g1t, parse_texinfo
from Scripts.resources.crop_native_item_atlas import crop_uv
from Scripts.resources.score_atlas_candidates import distance


def main():
    p = argparse.ArgumentParser(description=__doc__)
    native=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/MountPoint_1/0x00176283.fdata/native")
    p.add_argument("--g1t",type=Path,default=native/"root_012800_35d04d04.g1t")
    p.add_argument("--texinfo",type=Path,default=native/"root_047603_c8d83a39.texinfo")
    p.add_argument("--references",type=Path,default=Path("UnPack/2.0.1/Resources/Items/Icons"))
    p.add_argument("--output",type=Path,default=Path("atlas14-preview"))
    args=p.parse_args()
    platform,textures=parse_g1t(args.g1t.read_bytes())
    rec=parse_texinfo(args.texinfo.read_bytes())
    if len(rec)!=14 or len(textures)!=2 or platform!=0x18:
        raise ValueError("unexpected secondary atlas structure")
    formats=[(t["width"],t["height"],t["format"]) for t in textures]
    if formats!=[(512,256,0x66),(128,128,0x0a)]:
        raise ValueError(f"unexpected secondary atlas formats: {formats}")
    if sorted(set(int(x["texture_layer_raw_u32"]) for x in rec))!=[0,1]:
        raise ValueError("unexpected TEXINFO layers")
    args.output.mkdir(parents=True,exist_ok=True)
    candidates=[]
    for layer,tex in enumerate(textures):
        # Format-specific ranges: block-linear candidate height is bounded by the image rows.
        layouts=["linear","gob1","gob2","gob4","gob8"] if layer==0 else ["linear","gob1","gob2","gob4","gob8","gob16"]
        entries=[e for e in rec if e["texture_layer_raw_u32"]==layer]
        for layout in layouts:
            try:
                binary=decode_png(tex["payload"],tex["width"],tex["height"],layout,tex["format"])
            except ValueError as e:
                candidates.append({"item_id":"","sprite_name":"","layer":layer,"layout":layout,
                                   "status":"UNSUPPORTED_LAYOUT","score":"","png":"","reason":str(e)})
                continue
            with Image.open(io.BytesIO(binary)) as im:
                surface=im.convert("RGBA")
            for entry in entries:
                name=entry["name"]
                item_id=int(name.split("_")[1])
                row={f"uv_{k}":str(entry[k]) for k in ("u0","v0","u1","v1")}
                crop,rect=crop_uv(surface,row)
                if crop.size!=(72,72):
                    raise ValueError(f"unexpected crop {name}: {crop.size}")
                path=args.output/(f"{name}__layer{layer}__{layout}.png")
                crop.save(path)
                reference=args.references/f"item_{item_id:04d}.png"
                score=distance(path,reference) if reference.exists() else None
                candidates.append({"item_id":item_id,"sprite_name":name,"layer":layer,
                                   "layout":layout,"status":"UNVERIFIED_CANDIDATE",
                                   "score":"" if score is None else score,
                                   "png":path.as_posix(),"reason":""})
    cols=["item_id","sprite_name","layer","layout","status","score","png","reason"]
    with (args.output/"candidate_manifest.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols)
        w.writeheader();w.writerows(candidates)
    groups=defaultdict(list)
    for c in candidates:
        if c["score"]!="":
            groups[(c["layer"],c["layout"])].append(c["score"])
    rankings=sorted([
        {"layer":layer,"layout":layout,"items":len(vals),"median_difference":round(median(vals),8)}
        for (layer,layout),vals in groups.items()],key=lambda x:(x["layer"],x["median_difference"]))
    summary={"source":str(args.g1t),"texinfo":str(args.texinfo),
             "total_texinfo_records":len(rec),"texture_formats":[hex(x[2]) for x in formats],
             "statuses":{t:sum(c["status"]==t for c in candidates) for t in set(c["status"] for c in candidates)},
             "rankings":rankings,"warning":"No candidate is claimed pixel-verified or committed as final."}
    (args.output/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
