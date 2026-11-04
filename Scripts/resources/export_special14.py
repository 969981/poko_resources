#!/usr/bin/env python3
"""Export 14 extra item PNG CANDIDATES from mixed-format source G1T atlas.

13 BC7 (GOB8) and one BGRA (GOB16). Does not overwrite proven 1,333
native item icons or the imported PokoHex reference directory.
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
from Scripts.resources.crop_native_item_atlas import crop_uv
from Scripts.resources.g1t_to_png import parse_g1t, parse_texinfo, decode_png
from Scripts.resources.score_atlas_candidates import distance


def main():
    root=Path("UnPack/2.0.1/Resources")
    base=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/MountPoint_1/0x00176283.fdata/native")
    path=base/"root_012800_35d04d04.g1t"
    texinfo=base/"root_047603_c8d83a39.texinfo"
    out=root/"Items/Native_2.0.1/Extra14Candidates"
    out.mkdir(parents=True,exist_ok=True)
    platform,layers=parse_g1t(path.read_bytes())
    records=parse_texinfo(texinfo.read_bytes())
    if platform!=0x18 or len(layers)!=2 or len(records)!=14:
        raise ValueError("unexpected secondary atlas container")
    expected=[(512,256,0x66,"gob8"),(128,128,0x0a,"gob16")]
    canvases=[]
    for layer, (w,h,fmt,layout) in zip(layers,expected):
        if (layer["width"],layer["height"],layer["format"])!=(w,h,fmt):
            raise ValueError(f"secondary atlas layer mismatch: {layer}")
        image=decode_png(layer["payload"],w,h,layout,fmt)
        with Image.open(io.BytesIO(image)) as im:
            canvases.append(im.convert("RGBA"))
    rows=[]
    ids=set()
    for record in records:
        item=int(record["name"].split("_")[1])
        if item in ids:raise ValueError(f"duplicate item {item}")
        ids.add(item)
        layer=int(record["texture_layer_raw_u32"])
        if layer not in (0,1): raise ValueError("invalid layer")
        uv={f"uv_{k}":str(record[k]) for k in ("u0","v0","u1","v1")}
        crop,box=crop_uv(canvases[layer],uv)
        if crop.size!=(72,72):raise ValueError(f"invalid icon dimensions {item}: {crop.size}")
        png=out/f"item_{item:04d}.png"
        crop.save(png)
        ref=root/"Items/Icons"/png.name
        score=distance(png,ref) if ref.exists() else None
        rows.append({"id":item,"name":record["name"],"record_index":record["record_index"],
                     "layer":layer,"layout":expected[layer][3],
                     "g1t_hash":"35d04d04","texinfo_hash":"c8d83a39",
                     "path":png.as_posix(),"sha256":hashlib.sha256(png.read_bytes()).hexdigest(),
                     "reference_distance":"" if score is None else score,
                     "status":"ORIGINAL_SOURCE_CANDIDATE_NOT_PIXEL_IDENTICAL"})
    if len(rows)!=14: raise ValueError("expected 14 native images")
    cols=list(rows[0])
    with (out/"manifest.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(rows)
    scores=[r["reference_distance"] for r in rows if r["reference_distance"]!=""]
    summary={"count":14,"source_g1t":path.as_posix(),"source_texinfo":texinfo.as_posix(),
             "layers":{"BC7_gob8":13,"BGRA_gob16":1},
             "ref_comparison":len(scores),"max_difference":max(scores) if scores else None,
             "median_difference":median(scores) if scores else None,
             "note":"These 14 source-derived PNG crops are in Extra14Candidates for visual review and do not overwrite formally reviewed Icons."}
    (out/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
