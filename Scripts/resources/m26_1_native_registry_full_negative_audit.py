#!/usr/bin/env python3
"""M26.1: negative evidence check of 62 missing PokoHex portraits against
ALL 629 original KIDS source objects' real source-qualified PNG candidates.

The 629 source OIDs represent a specific native 2.0.1 icon registry, NOT
every image in every missing FDATA platform or future DLC. "No matching
registry PNG" cannot be promoted to "species absent from game".
"""
from __future__ import annotations
import csv
import hashlib
import json
from collections import Counter,defaultdict
from pathlib import Path
from PIL import Image,ImageChops,ImageStat

R=Path("UnPack/2.0.1/Resources")
M26=R/"Villagers/Native_2.0.1/M26"
M25=R/"Pokemon/NativeRecoveryM25"
REGISTRY=M25/"m25_8_complete_native_629_kids_icon_source_index.csv"
ROSTER=M26/"m26_62_third_party_portrait_roster.csv"
LEGACY=R/"Pokemon/NativeCandidates/pokemon_native_manifest.csv"
RECOVER=M25/"m25_5_native_icon_export_manifest.csv"
LIMIT=0.015
GAP=0.015
FIELDS=(
    "reference_pokohex_portrait_id","reference_name","reference_png",
    "best_original_native_source_oid","best_original_texture_oid","best_original_array_index",
    "best_original_texture_name","best_original_png_path",
    "best_normalized_mae","second_best_normalized_mae","top_three_source_oid_slots",
    "distance_threshold","separation_threshold",
    "is_confident_visual_match_in_629_source_registry",
    "original_native_game_id_verified","conclusion",
)

def read(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def thumb(p):
    with Image.open(p) as f:
        source=f.convert("RGBA")
        if source.width<8 or source.height<8:raise ValueError("Unusable original image")
        white=Image.alpha_composite(Image.new("RGBA",source.size),source)
        return white.resize((32,32),Image.Resampling.LANCZOS)

def mae(a,b):
    return sum(ImageStat.Stat(ImageChops.difference(a,b)).mean)/(4*255)

def run():
    nodes=read(REGISTRY)
    roster=read(ROSTER)
    legacy=read(LEGACY)
    recovered=read(RECOVER)
    if (len(nodes),len(roster),len(legacy),len(recovered))!=(629,62,609,26):
        raise ValueError("M25 canonical original icon registry changed")
    checks={}
    for row in legacy:
        p=row["png_path"]
        if p and row["png_sha256"]:
            if p in checks and checks[p]!=row["png_sha256"]:
                raise ValueError("Original M21 PNG collision")
            checks[p]=row["png_sha256"]
    for row in recovered:
        checks[row["png_file"]]=row["png_sha256"]
    files=defaultdict(list)
    for row in nodes:
        if not row["original_png_candidates"]:
            raise ValueError("Original source KIDS icon without a PNG candidate")
        for path in row["original_png_candidates"].split(";"):
            if not path:continue
            files[path].append(row)
    if len(files)!=635:
        raise ValueError(f"Expected 609+26 original source-linked PNG candidates, got {len(files)}")
    if set(files)!=set(checks):
        raise ValueError("M25 complete native index and original PNG hash manifest do not cover identical paths")
    images=[]
    for i,(path,attrs) in enumerate(sorted(files.items())):
        raw=Path(path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=checks[path]:
            raise ValueError(f"Original PNG SHA256 mismatch: {path}")
        images.append((path,attrs[0],thumb(path)))
    results=[]
    for x in sorted(roster,key=lambda a:int(a["reference_pokohex_portrait_id"])):
        ref_path=x["reference_png"]
        q=thumb(ref_path)
        scored=sorted(
            [(mae(q,img),path,row) for path,row,img in images],
            key=lambda t:(t[0],t[2]["source_oid"],t[1]))
        first=scored[0]
        # Use different Source OID for next ranked competitor; a PNG with
        # multiple alias names cannot constitute independent evidence.
        next_best=next((r for r in scored[1:] if r[2]["source_oid"]!=first[2]["source_oid"]),None)
        second=next_best[0] if next_best else 1
        confident=first[0]<=LIMIT and (second-first[0])>=GAP
        top=[(f"{v[2]['source_oid']}:{v[2]['original_array_index']}:{v[0]:.8f}")
             for v in scored[:3]]
        results.append({
            "reference_pokohex_portrait_id":x["reference_pokohex_portrait_id"],
            "reference_name":x["reference_pokohex_english_name"],
            "reference_png":ref_path,
            "best_original_native_source_oid":first[2]["source_oid"],
            "best_original_texture_oid":first[2]["target_texture_oid"],
            "best_original_array_index":first[2]["original_array_index"],
            "best_original_texture_name":first[2]["original_texture_name_variants"],
            "best_original_png_path":first[1],
            "best_normalized_mae":f"{first[0]:.8f}",
            "second_best_normalized_mae":f"{second:.8f}",
            "top_three_source_oid_slots":";".join(top),
            "distance_threshold":LIMIT,"separation_threshold":GAP,
            "is_confident_visual_match_in_629_source_registry":int(confident),
            "original_native_game_id_verified":"",
            "conclusion":"CONFIDENT_IMAGE_CANDIDATE_NOT_GAME_ID_PROVEN" if confident
                else "NO_CONFIDENT_IMAGE_MATCH_IN_629_NATIVE_SOURCE_OIDS",
        })
    stat=Counter(r["conclusion"] for r in results)
    summary={
        "version":"2.0.1",
        "original_source_kids_oid_count":len(nodes),
        "original_source_linked_distinct_png_files":len(files),
        "original_png_sha256_verified":len(images),
        "original_reference_portraits_rechecked":len(roster),
        "new_confident_visual_matches":stat.get("CONFIDENT_IMAGE_CANDIDATE_NOT_GAME_ID_PROVEN",0),
        "still_no_confident_image_match_in_scope":stat.get("NO_CONFIDENT_IMAGE_MATCH_IN_629_NATIVE_SOURCE_OIDS",0),
        "method":"32x32 alpha-white normalized RGBA MAE, <=0.015 and >=0.015 distinct source-OID gap; source SHA256",
        "not_exhaustive_of_other_original_FDATA_containers":True,
        "game_species_ids_verified":0,
        "game_villager_ids_verified":0,
        "warning":"This tests only the complete currently indexed 629 native KIDS icon source OIDs; it cannot show whether PokoHex's 62 named references are in another original platform, hidden DLC, or newer content.",
    }
    M26.mkdir(parents=True,exist_ok=True)
    with (M26/"m26_1_62_vs_complete_629_icon_registry.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();writer.writerows(results)
    (M26/"m26_1_original_icon_registry_negative_audit.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

if __name__=="__main__":run()
