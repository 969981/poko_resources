#!/usr/bin/env python3
"""M25.5: restore 26 overlooked original Pokémon G1T/TEXINFO PNG candidates.

Native original TEXINFO is already physically stored as decoded
root_XXXXXX_HASH.fdata_idrk.bin; only its .texinfo alias/export was omitted.
Read the original decoded payload directly, parse sprite name + UV, verify
the original 2.0.1 G1T and export a cropped PNG with exact source trail.
Never infer species ID from the filename, a KIDS array slot, or a PokoHex ID.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter,defaultdict
from functools import lru_cache
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops, ImageStat

from Scripts.resources.g1t_to_png import parse_texinfo,parse_g1t,decode_png
from Scripts.resources.crop_native_item_atlas import crop_uv
from Scripts.resources.export_native_pokemon_icons import layout_for_bc7

R=Path("UnPack/2.0.1/Resources")
M25=R/"Villagers/Native_2.0.1/M25"
TEXINDEX=M25/"m25_4_26_texture_hash_rdb_provenance.csv"
SOURCEINDEX=M25/"m25_3_26_original_source_to_texture_objects.csv"
MISSING=M25.parent.parent/"M22/m22_unresolved_79_source_targets.csv"
OUT=R/"Pokemon/NativeRecoveryM25"

FIELDS=(
    "original_array_slot","original_source_oid","original_texture_oid",
    "texture_name_original_texinfo","original_name_family","texinfo_hash","g1t_hash",
    "texinfo_decoded_file","texinfo_original_sha256","g1t_native_file","g1t_original_sha256",
    "texinfo_record_index","texture_layer","g1t_platform_hex","format_hex",
    "canvas_width","canvas_height","source_uv_rect","crop_dimensions",
    "png_file","png_sha256","nontransparent_pixels","status","failure_reason",
    "native_species_id_verified","native_villager_id_verified",
)
THUMB=32

def csvrows(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def one_path(paths,ext,slot):
    choices=[x for x in paths if x and x.endswith(ext)]
    if len(choices)!=1:
        raise ValueError(f"Ambiguous original {ext} for native array slot {slot}: {choices}")
    return Path(choices[0])

def selected_sources():
    original=csvrows(SOURCEINDEX)
    source={int(r["original_array_slot"]):r for r in original}
    if len(source)!=26:raise ValueError("M25.3 source count changed")
    rdb=csvrows(TEXINDEX)
    by_slot=defaultdict(dict)
    for entry in rdb:
        i=int(entry["array_slot"])
        kind=entry["resource_extension_expected"]
        if kind in by_slot[i]:raise ValueError(f"Duplicate original RDB record for {i}:{kind}")
        by_slot[i][kind]=entry
    if set(by_slot)!=set(source):raise ValueError("M25.4 original RDB record list incomplete")
    selected=[]
    for i,row in sorted(source.items()):
        info=by_slot[i]
        if set(info)!={"g1t","texinfo"}:raise ValueError(f"Missing original resource type for {i}")
        g,t=info["g1t"],info["texinfo"]
        for kind,rec in (("g1t",g),("texinfo",t)):
            if rec["original_rdb_record_found"]!="True" or rec["original_type_matches_expected"]!="True":
                raise ValueError(f"Original RDB source not type validated: {i}:{kind}")
            if rec["original_fdata_name"]!="0x00011c54.fdata" or rec["original_platform_flag"]!="ffff":
                raise ValueError(f"Unexpected original FDATA platform or source {i}:{kind}")
        texpath=one_path(t["matching_decoded_artifact_paths"].split(";"),".bin",i)
        g1tpath=one_path(row["original_g1t_file_paths"].split(";"),".g1t",i)
        if g1tpath.as_posix()!=g["expected_native_alias"]:
            raise ValueError(f"Original G1T path from native graph != RDB alias {i}")
        if t["native_resource_hash"]!=row["target_texinfo_hash"] or g["native_resource_hash"]!=row["target_g1t_hash"]:
            raise ValueError("Native object resource hashes don't agree with original RDB")
        selected.append({"slot":i,"texture":row,"original_texinfo":texpath,"original_g1t":g1tpath,
                         "texinfo_rdb":t,"g1t_rdb":g})
    return selected

def plan(path):
    selected=selected_sources()
    names=sorted({p for r in selected for p in (
        r["original_texinfo"].as_posix(),r["original_g1t"].as_posix())})
    if len(names)!=52 or len(selected)!=26:
        raise ValueError("Original 26 TEXINFO + G1T paths not unique")
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text("\n".join("/"+x for x in names)+"\n",encoding="utf-8")
    print(json.dumps({"native_slots":len(selected),"required_sparse_paths":len(names),
                      "sparse_file":str(path)},ensure_ascii=False,indent=2))

@lru_cache(maxsize=32)
def read_g1t(path):
    blob=Path(path).read_bytes()
    digest=hashlib.sha256(blob).hexdigest()
    platform,tex=parse_g1t(blob)
    if platform!=0x18:raise ValueError(f"Wrong original G1T platform: {platform:#x}")
    return digest,platform,tex

def whitened_thumb(path):
    with Image.open(path) as pic:
        img=pic.convert("RGBA")
        # Same alpha-aware 32x32 normalization as M21/M22; transparent
        # RGB must not influence the comparison.
        img=Image.alpha_composite(Image.new("RGBA",img.size),img)
        return img.resize((THUMB,THUMB),Image.Resampling.LANCZOS)

def err(a,b):
    return sum(ImageStat.Stat(ImageChops.difference(a,b)).mean)/(4*255)

def original_visual_review(manifest):
    valid=[x for x in manifest if x["png_file"]]
    refs=csvrows(MISSING)
    if len(refs)!=79:raise ValueError("M22 original 79-reference baseline changed")
    candidates=[(r,whitened_thumb(r["png_file"])) for r in valid]
    result=[]
    for r in refs:
        name=Path(r["reference_png"])
        if hashlib.sha256(name.read_bytes()).hexdigest()!=r["reference_sha256"]:
            raise ValueError(f"Reference image SHA changed: {name}")
        reference=whitened_thumb(name)
        ranked=sorted(((err(reference,im),x) for x,im in candidates),
                      key=lambda x:(x[0],int(x[1]["original_array_slot"])))
        best=ranked[0] if ranked else None
        second=ranked[1] if len(ranked)>1 else None
        d=best[0] if best else 1
        prior=float(r["old_m21_nearest_mae"])
        next_gap=(second[0]-d) if second else 1
        status=("NEW_VISUAL_NEAR_IDENTICAL_CANDIDATE_REVIEW"
                if best and d<=.015 and next_gap>=.015 and prior-d>=.015
                else "NO_STRONG_NEW_VISUAL_IDENTITY_CANDIDATE")
        result.append({
            "portrait_id_pokohex":r["portrait_id_pokohex"],
            "portrait_reference_png":r["reference_png"],
            "prior_m21_best_distance":r["old_m21_nearest_mae"],
            "best_m25_original_array_slot":best[1]["original_array_slot"] if best else "",
            "best_m25_texture_name":best[1]["texture_name_original_texinfo"] if best else "",
            "best_m25_png":best[1]["png_file"] if best else "",
            "best_m25_source_oid":best[1]["original_source_oid"] if best else "",
            "best_m25_target_oid":best[1]["original_texture_oid"] if best else "",
            "best_m25_distance":f"{d:.8f}" if best else "",
            "second_m25_distance":f"{second[0]:.8f}" if second else "",
            "status":status,
            "native_villager_id_proven":"",
        })
    with (M25/"m25_5_79_portrait_visual_crosscheck.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(result[0]))
        w.writeheader();w.writerows(result)
    return result

def main_run():
    source=selected_sources()
    OUT.mkdir(parents=True,exist_ok=True)
    reports=[]
    for record in source:
        i=record["slot"]
        item=record["texture"]
        tif=record["original_texinfo"]
        gtf=record["original_g1t"]
        row=dict.fromkeys(FIELDS,"")
        row.update(original_array_slot=i,original_source_oid=item["native_source_oid"],
                   original_texture_oid=item["native_target_oid"],
                   texinfo_hash=item["target_texinfo_hash"],g1t_hash=item["target_g1t_hash"],
                   texinfo_decoded_file=tif.as_posix(),g1t_native_file=gtf.as_posix(),
                   status="PENDING",native_species_id_verified="",native_villager_id_verified="")
        try:
            b=tif.read_bytes()
            if len(b)!=int(record["texinfo_rdb"]["original_unpacked_bytes"]):
                raise ValueError("Original RDB uncompressed TEXINFO size mismatch")
            r= parse_texinfo(b)
            if len(r)!=1:
                raise ValueError(f"Unexpected original TEXINFO record count {len(r)}; requires atlas multi-record handling")
            rec=r[0]
            if rec["uv_status"]!="RECT_OK":
                raise ValueError("Original UV rectangle invalid")
            name=rec["name"]
            if not (name.startswith("icon_poke_") or name=="icon_poke_blank"):
                raise ValueError(f"Not an original Pokemon-icon family name: {name}")
            row.update(texture_name_original_texinfo=name,
                       original_name_family="pokemon_uni" if name.startswith("icon_poke_uni_") else "pokemon",
                       texinfo_original_sha256=hashlib.sha256(b).hexdigest(),
                       texinfo_record_index=rec["record_index"],
                       texture_layer=rec["texture_layer_raw_u32"],
                       source_uv_rect=",".join(f"{rec[k]:.8g}" for k in ("u0","v0","u1","v1")))
            g1tsha,platform,textures=read_g1t(str(gtf))
            row.update(g1t_platform_hex=hex(platform),g1t_original_sha256=g1tsha)
            layer=rec["texture_layer_raw_u32"]
            if layer>=len(textures):raise ValueError("Original TEXINFO layer exceeds G1T layer count")
            tex=textures[layer]
            fmt,w,h=tex["format"],tex["width"],tex["height"]
            if fmt!=0x66:
                raise ValueError(f"Unsupported original sprite format: 0x{fmt:02x}")
            row.update(format_hex=hex(fmt),canvas_width=w,canvas_height=h)
            imagebytes=decode_png(tex["payload"],w,h,layout_for_bc7(h),fmt)
            with Image.open(io.BytesIO(imagebytes)) as image:
                crop,_=crop_uv(image.convert("RGBA"),{
                    f"uv_{k}":str(rec[k]) for k in ("u0","v0","u1","v1")})
            if min(crop.size)<8 or max(crop.size)>2048:
                raise ValueError(f"Unexpected original image dimensions {crop.size}")
            native_name=re.sub(r"[^a-zA-Z0-9_-]","_",name)
            target=OUT/"Icons"/f"slot{i:04d}__{native_name}__{row['texinfo_hash']}__{row['g1t_hash']}.png"
            target.parent.mkdir(parents=True,exist_ok=True)
            crop.save(target,"PNG")
            with Image.open(target) as check:check.verify()
            alpha=crop.getchannel("A")
            count=sum(v>0 for v in alpha.getdata())
            row.update(png_file=target.as_posix(),
                       png_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                       crop_dimensions=f"{crop.width}x{crop.height}",
                       nontransparent_pixels=count,
                       status="ORIGINAL_NATIVE_SOURCE_PNG_CANDIDATE" if count else "ORIGINAL_NATIVE_TRANSPARENT_PLACEHOLDER")
        except (OSError,ValueError,IndexError,KeyError) as exc:
            row.update(status="SOURCE_OR_DECODE_FAILED",failure_reason=str(exc))
        reports.append(row)
    with (OUT/"m25_5_native_icon_export_manifest.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(reports)
    valid=[x for x in reports if x["png_file"]]
    if valid:
        sheet=Image.new("RGB",(6*175,((len(valid)+5)//6)*205),(246,246,246))
        pen=ImageDraw.Draw(sheet)
        for j,r in enumerate(valid):
            x=(j%6)*175;y=(j//6)*205
            with Image.open(r["png_file"]) as img: thumb=img.convert("RGBA")
            thumb.thumbnail((160,161),Image.Resampling.LANCZOS)
            white=Image.new("RGBA",thumb.size,(255,255,255,255));white.alpha_composite(thumb)
            sheet.paste(white.convert("RGB"),(x+(175-thumb.width)//2,y))
            pen.text((x+4,y+166),r["texture_name_original_texinfo"][:22],fill=(20,20,20))
            pen.text((x+4,y+183),f"slot {r['original_array_slot']} {r['g1t_hash']}",fill=(65,65,65))
        sheet.save(OUT/"contact_sheet_26.png")
    cross=original_visual_review(reports) if valid else []
    report={
        "version":"2.0.1",
        "original_registry_unmatched_slots":26,
        "original_TEXINFO_decoded_bin_inputs":26,
        "original_G1T_native_inputs":26,
        "native_png_created":len(valid),
        "native_nontransparent_pngs":sum(int(x["nontransparent_pixels"] or 0)>0 for x in reports),
        "original_texture_names_from_TEXINFO":[x["texture_name_original_texinfo"] for x in reports if x["texture_name_original_texinfo"]],
        "source_statuses":dict(Counter(x["status"] for x in reports)),
        "failed_sources":[{"slot":x["original_array_slot"],"error":x["failure_reason"]}
                          for x in reports if x["status"]=="SOURCE_OR_DECODE_FAILED"],
        "m22_reference_portraits_rechecked":len(cross),
        "new_strong_visual_matches_to_previous_79":sum(
            x["status"]=="NEW_VISUAL_NEAR_IDENTICAL_CANDIDATE_REVIEW" for x in cross),
        "real_native_game_species_id_bindings_proven":0,
        "real_native_villager_id_bindings_proven":0,
        "warning":"Native PNG names and pixels are recovered; their filename numerals/array slots are not game-ID or PokoHex villager-ID proof.",
    }
    (OUT/"m25_5_native_icon_export_summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (M25/"m25_5_recovery_summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="original_texture_names_from_TEXINFO"},ensure_ascii=False,indent=2))
    if not valid:
        raise ValueError("No original source icon PNG candidates decoded")
    return report

def selftest():
    assert len(FIELDS)==23
    assert THUMB==32
    print("M25.5 original source encoding and report schema sanity passed")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan",type=Path)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    elif a.plan:plan(a.plan)
    else:main_run()

if __name__=="__main__":main()
