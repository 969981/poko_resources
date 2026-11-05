#!/usr/bin/env python3
"""M25.3: decode exact source->target native KIDS object references for 26 holes.

Read 26 original array values in the 3543-value 0x34CBB458 registry and
follow typed 0x2856A1B3 to texture objects. Validate their native G1T and
TEXINFO scalar hashes and check original repository file names via Git tree.
This does not prove game Pokédex species IDs or portrait identity.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import struct
import subprocess
from collections import Counter,defaultdict
from pathlib import Path
from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

ROOT=Path("UnPack/2.0.1/Resources")
NATIVE=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native")
ORIGINAL=NATIVE/"root_019167_50ae86ef.kidsobjdb"
OUT=ROOT/"Villagers/Native_2.0.1/M25"
GAPS=OUT/"m25_2_26_unmatched_native_icon_registry.csv"
HASH="86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541"
TYPED=0x79991E79
EDGE=0x2856A1B3
G1T=0xC8BB66DA
TEXINFO=0x2276FC56

def rows(path):
    with path.open(encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))

def checked_scalar(original,node,field):
    obj=node["fields"].get(field)
    if not obj or obj["kind"] not in (4,5) or obj["count"]!=1:
        return None
    at=obj["offset"]
    if not 0<=at<len(original)-3:raise ValueError("Out-of-range original native object")
    native=struct.unpack_from("<I",original,at)[0]
    if native!=obj["u32"]:raise ValueError("Original typed parser value diverges from native source bytes")
    return native

def source_paths():
    names=subprocess.check_output(
        ["git","ls-tree","-r","--name-only","HEAD","--",
         "UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE"],
         text=True,encoding="utf-8").splitlines()
    by_ext=defaultdict(list)
    for name in names:
        m=re.search(r"_([0-9a-f]{8})\.(g1t|texinfo)$",name,re.I)
        if m:by_ext[(m.group(1).lower(),m.group(2).lower())].append(name)
    return by_ext,len(names)

def analyze():
    b=ORIGINAL.read_bytes()
    if hashlib.sha256(b).hexdigest()!=HASH:
        raise ValueError("Original KIDS source SHA256 mismatch")
    _,db=parse_kids(b)
    gap=rows(GAPS)
    if len(gap)!=26 or len({int(x["native_array_index"]) for x in gap})!=26:
        raise ValueError("M25.2 26 source entries missing")
    disk,total_files=source_paths()
    result=[]
    for entry in sorted(gap,key=lambda x:int(x["native_array_index"])):
        raw_oid=int(entry["original_u32"],16)
        source=db.get(raw_oid)
        if not source: raise ValueError(f"M25.2 source OID absent from original main source: {raw_oid:08x}")
        if source["type"]!=TYPED:raise ValueError(f"Unknown original type for source {raw_oid:08x}")
        g1src=checked_scalar(b,source,G1T)
        texsrc=checked_scalar(b,source,TEXINFO)
        target=checked_scalar(b,source,EDGE)
        if target is None:raise ValueError("Original source has no 0x2856A1B3 typed property")
        target_node=db.get(target)
        target_source_file=ORIGINAL.as_posix()
        if target_node is None:
            # Do not infer a target type or G1T without the original node.
            target_status="TARGET_NOT_IN_ORIGINAL_PARENT_DATABASE"
            tg1=ttx=None;target_kind=None;target_offset=None
        else:
            target_status="TARGET_ORIGINAL_OBJECT_PRESENT"
            target_kind=target_node["type"]
            target_offset=target_node["offset"]
            tg1=checked_scalar(b,target_node,G1T)
            ttx=checked_scalar(b,target_node,TEXINFO)
        gh=f"{tg1:08x}" if tg1 is not None else ""
        th=f"{ttx:08x}" if ttx is not None else ""
        gpaths=disk.get((gh,"g1t"),[]) if gh else []
        tpaths=disk.get((th,"texinfo"),[]) if th else []
        srcpos=source["fields"][EDGE]["offset"]
        if struct.unpack_from("<I",b,srcpos)[0]!=target:
            raise ValueError(f"Original source u32 edge bytes changed: {raw_oid:08x}")
        row={
            "original_array_slot":int(entry["native_array_index"]),
            "array_block":entry["index_block"],
            "original_array_value_offset":entry["original_u32_byte_offset"],
            "native_source_oid":f"{raw_oid:08x}",
            "source_object_original_offset":source["offset"],
            "native_source_node_type":f"{source['type']:08x}",
            "source_g1t_value":f"{g1src:08x}" if g1src is not None else "",
            "source_texinfo_value":f"{texsrc:08x}" if texsrc is not None else "",
            "original_property_hash":f"{EDGE:08x}",
            "original_edge_value_offset":srcpos,
            "native_target_oid":f"{target:08x}",
            "target_node_status":target_status,
            "native_target_node_type":f"{target_kind:08x}" if target_kind is not None else "",
            "target_node_original_offset":target_offset if target_offset is not None else "",
            "target_g1t_hash":gh,
            "target_texinfo_hash":th,
            "original_g1t_file_paths":";".join(gpaths),
            "original_texinfo_file_paths":";".join(tpaths),
            "has_original_g1t_tracked_file":int(bool(gpaths)),
            "has_original_texinfo_tracked_file":int(bool(tpaths)),
            "prev_known_sprite_name":entry["original_neighbor_previous_sprite"],
            "next_known_sprite_name":entry["original_neighbor_next_sprite"],
            "verified_native_species_id":"",
            "verified_native_villager_id":"",
            "evidence_grade":"ARRAY_BYTES_TO_SOURCE_OBJECT_TO_TYPED_TARGET_BYTES",
        }
        result.append(row)
    stats=Counter(x["target_node_status"] for x in result)
    coverage=Counter((x["has_original_g1t_tracked_file"],x["has_original_texinfo_tracked_file"]) for x in result)
    result_report={
        "original_root_sha256":HASH,
        "original_array_26_gap_slots":len(result),
        "source_object_type_checked":f"{TYPED:08x}",
        "source_typed_edge_property_hash":f"{EDGE:08x}",
        "typed_original_target_statuses":dict(stats),
        "target_nonzero_g1t_hash_count":sum(bool(x["target_g1t_hash"] and x["target_g1t_hash"]!="00000000") for x in result),
        "target_nonzero_texinfo_hash_count":sum(bool(x["target_texinfo_hash"] and x["target_texinfo_hash"]!="00000000") for x in result),
        "tracked_original_native_source_count":total_files,
        "tracked_original_source_coverage_by_g1t_texinfo":{
            f"g1t_{a}_texinfo_{b}":v for (a,b),v in sorted(coverage.items())},
        "native_species_ids_proven":0,
        "native_villager_ids_proven":0,
        "warning":"A texture resource found by an adjacent gap is not a proven ID or decoded original PNG until source G1T and TEXINFO bytes and images are verified.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"m25_3_26_original_source_to_texture_objects.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(result[0]))
        w.writeheader();w.writerows(result)
    (OUT/"m25_3_26_texture_object_summary.json").write_text(
        json.dumps(result_report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result_report,ensure_ascii=False,indent=2))
    return result_report

def selftest():
    # A parser may not pretend a value is a G1T/TEXINFO when a typed
    # property descriptor is absent. Data validation is against original raw.
    node={"fields":{}}
    assert checked_scalar(b"",node,G1T) is None
    assert checked_scalar(b"",node,EDGE) is None
    print("PASS fail-closed missing typed property access")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest()
    else:analyze()

if __name__=="__main__":main()
