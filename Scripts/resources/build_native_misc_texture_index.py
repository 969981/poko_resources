#!/usr/bin/env python3
"""Build a source-traceable 2.0.1 non-item/non-Pokémon sprite index.

The classification is strictly a native NAME heuristic, never a confirmed
gameplay/material identity. Link TEXINFO -> KIDSOBJDB index -> G1T where both
hashes and a unique original physical G1T path exist in the Git tree.
"""
from __future__ import annotations
import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path("UnPack/2.0.1/Resources")
FIELDS=[
    "texture_name","family","category_candidate","category_evidence",
    "texinfo_hash","texinfo_path","record_index","record_count","layer",
    "uv_u0","uv_v0","uv_u1","uv_v1","uv_status",
    "g1t_hash","g1t_path","object_hash","objdb_file","status",
]


def read(path, delimiter=","):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f,delimiter=delimiter))


def eligible(name):
    low=name.lower()
    return bool(name) and not re.match(r"^item_\d+(?:_|$)",low) and not low.startswith("icon_poke_")

def family_kind(name):
    name=name.lower()
    if "material" in name:
        return "material_name_candidate"
    if name.startswith(("icon_","ui_","hud_","menu_","button_")):
        return "ui_icon_name_candidate"
    if name.startswith(("shop_","food_","seal_","still_","map_","layout_")):
        return "ui_gameplay_name_candidate"
    return "other_native_sprite_name"


def index_rows(texrows, layoutrows, git_tree):
    native=set(p.lstrip("./") for p in git_tree if p.endswith((".g1t",".texinfo")))
    g1t=defaultdict(list)
    for path in sorted(native):
        if path.endswith(".g1t"):
            hash_=Path(path).stem.rsplit("_",1)[-1].lower()
            g1t[hash_].append(path)
    pairs=defaultdict(list)
    for row in layoutrows:
        pairs[(row["texinfo_hash"].lower(),row["g1t_hash"].lower())].append(row)
    candidates=defaultdict(list)
    for (th,gh),edges in pairs.items():
        if th!="00000000" and gh!="00000000":
            candidates[th].append((gh,edges))
    result=[]
    for record in texrows:
        name=record["texture_name"]
        if not eligible(name):
            continue
        t_path=record["texinfo_path"].removeprefix("./")
        th=Path(t_path).stem.rsplit("_",1)[-1].lower()
        links=candidates.get(th,[])
        kind=family_kind(name)
        # Only one unique native object/hash edge is acceptable. TEXINFO->G1T
        # identity is ambiguous if multiple G1T hashes reference this TEXINFO.
        edges=[(gh,rows[0]) for gh,rows in links if len(rows)==1]
        if t_path not in native:
            status,found="NATIVE_TEXINFO_MISSING_FROM_GIT_TREE",None
        elif len(links)!=1 or len(edges)!=1:
            status,found="MISSING_OR_AMBIGUOUS_KIDSOBJDB_INDEX_EDGE",None
        elif len(g1t[edges[0][0]])!=1:
            status,found="G1T_ABSENT_OR_AMBIGUOUS_IN_PRIMARY_PACK",None
        elif record["uv_status"]!="RECT_OK":
            status,found="TEXINFO_UV_REVIEW",None
        else:
            status,found="INDEXED_ORIGINAL_TEXINFO_G1T_PAIR",edges[0]
        gh,edge=(found if found else ("",{}))
        result.append({
            "texture_name":name,"family":record["family"],
            "category_candidate":kind,
            "category_evidence":"NAME_HEURISTIC_ONLY_NOT_GAMEPLAY_TYPE",
            "texinfo_hash":th,"texinfo_path":t_path,
            "record_index":record["record_index"],"record_count":record["record_count"],
            "layer":record["texture_layer_raw_u32"],
            **{f"uv_{key}":record[f"atlas_{key}"] for key in ("u0","v0","u1","v1")},
            "uv_status":record["uv_status"],
            "g1t_hash":gh,"g1t_path":g1t[gh][0] if found else "",
            "object_hash":edge.get("object_hash",""),"objdb_file":edge.get("objdb_file",""),
            "status":status,
        })
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--texinfo",type=Path,default=ROOT/"Textures/texinfo_names.csv")
    p.add_argument("--layout",type=Path,default=ROOT/"Textures/Indexes/layout-textures.tsv")
    p.add_argument("--git-tree",type=Path,required=True)
    p.add_argument("--out",type=Path,default=ROOT/"Textures/Indexes/native_misc_texture_index.csv")
    args=p.parse_args()
    source=read(args.texinfo)
    layout=read(args.layout,"\t")
    tree=args.git_tree.read_text(encoding="utf-8").splitlines()
    allrows=index_rows(source,layout,tree)
    if not source or not layout or not tree or not allrows:
        raise ValueError("Missing input/source coverage; cannot write an empty index")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(allrows)
    report={
        "game_version":"2.0.1","input_texinfo_records":len(source),
        "non_item_non_pokemon_records":len(allrows),
        "linked_native_g1t":sum(r["status"]=="INDEXED_ORIGINAL_TEXINFO_G1T_PAIR" for r in allrows),
        "statuses":dict(Counter(r["status"] for r in allrows)),
        "name_heuristic_categories":dict(Counter(r["category_candidate"] for r in allrows)),
        "top_families":dict(Counter(r["family"] for r in allrows).most_common(30)),
        "material_identity_verified":False,
        "warning":"Category is from resource names only. KIDSOBJDB pairs are native index edges; pixel/decode evidence requires per-file G1T validation."
    }
    args.out.with_name("native_misc_texture_summary.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
