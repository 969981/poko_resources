#!/usr/bin/env python3
"""M28.3 original Pokopia KIDS icon lookup CLI, no inferred game species IDs.

Reproducible examples:
  python -m Scripts.resources.m28_3_kids_icon_lookup --name icon_poke_0043_00_00_00
  python -m Scripts.resources.m28_3_kids_icon_lookup --slot 455
  python -m Scripts.resources.m28_3_kids_icon_lookup --verify-all

A number in a TEXINFO resource name is NOT an authenticated game species ID.
Every result is checked against original 2.0.1 KIDSOBJDB bytes, 3543
paired u32s and the M25 typed Source OID -> texture -> PNG index.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import struct
from pathlib import Path

from Scripts.resources.m27_reverse_decimal_hash31 import (
    h31,reverse_four,power31,PIN,KEY_HASH,VALUE_HASH,OWNER,TYPE,SIZE,
    FAMILIES,
)
from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

R=Path("UnPack/2.0.1/Resources")
RAW=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native/root_019167_50ae86ef.kidsobjdb")
PAIRS=R/"Villagers/Native_2.0.1/M26/m26_4_original_3543_parallel_key_value_pairs.csv"
CONSTANTS=R/"Villagers/Native_2.0.1/M27/m27_hash31_candidate_family_constants.json"
INDEX=R/"Pokemon/NativeRecoveryM25/m25_8_complete_native_629_kids_icon_source_index.csv"
PROOF=R/"Villagers/Native_2.0.1/M27/m27_626_native_icon_hash31_template_validation.csv"
NAME=re.compile(r"^icon_poke_(uni_)?(\d{4})_(\d{2})_(\d{2})_(\d{2})(_nh)?$")
KEY_MASK=0xffffffff

def read_csv(path):
    with path.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def load():
    data=RAW.read_bytes()
    if hashlib.sha256(data).hexdigest()!=PIN:
        raise ValueError("Original KIDS 2.0.1 database SHA256 changed")
    _,objects=parse_kids(data)
    obj=objects.get(OWNER)
    if obj is None or obj["type"]!=TYPE:raise ValueError("Original class/source OID changed")
    kp=obj["fields"][KEY_HASH]
    vp=obj["fields"][VALUE_HASH]
    if kp["count"]!=SIZE or vp["count"]!=SIZE:
        raise ValueError("Original KIDS paired arrays changed")
    kv=struct.unpack_from("<"+"I"*SIZE,data,kp["offset"])
    vv=struct.unpack_from("<"+"I"*SIZE,data,vp["offset"])
    exported=read_csv(PAIRS)
    if len(exported)!=SIZE:raise ValueError("M26 original byte crosswalk incomplete")
    for idx,r in enumerate(exported):
        if (int(r["native_array_index"])!=idx or
             int(r["original_key_u32"],16)!=kv[idx] or
             int(r["original_value_u32"],16)!=vv[idx]):
            raise ValueError(f"Original byte crosswalk mismatch at {idx}")
    original=read_csv(INDEX)
    if len(original)!=629:raise ValueError("M25 typed texture provenance not complete")
    by_slot={}
    for row in original:
        if row["original_owner_oid"]=="b4a1803b":
            idx=int(row["original_array_index"])
            if idx in by_slot:raise ValueError("Source OID mapped twice")
            if int(row["source_oid"],16)!=vv[idx]:
                raise ValueError("Original KIDS source OID and M25 texture provenance disagree")
            by_slot[idx]=row
    if len(by_slot)!=628:raise ValueError("M25 628 original KIDS slots not verified")
    all_constants=json.loads(CONSTANTS.read_text(encoding="utf-8"))
    constants={(c["family"],c["variant"]):c for c in all_constants}
    if len(constants)!=14:raise ValueError("M27 14 string model groups missing")
    by_key={v:i for i,v in enumerate(kv)}
    if len(by_key)!=SIZE:raise ValueError("Original key collisions require explicit handling")
    return {"keys":kv,"values":vv,"sources":by_slot,"constants":constants,"key_to_slot":by_key}

def parse_name(name):
    m=NAME.fullmatch(name)
    if not m:
        raise ValueError("Unsupported name, expected icon_poke_0043_00_00_00 or icon_poke_uni_0043_00_00_00")
    family="uni" if m.group(1) else "normal"
    n=m.group(2)
    variant="_".join(m.group(j) for j in (3,4,5))+(m.group(6) or "")
    return family,n,variant

def slot_info(db,slot):
    if not 0<=slot<SIZE:raise ValueError("Native array index out of bounds [0..3542]")
    source=db["sources"].get(slot)
    data={
        "version":"2.0.1",
        "original_kids_source_class":"0x9D1AFA46",
        "original_class_source_oid":"0xB4A1803B",
        "native_original_array_index":slot,
        "original_key_u32":f"{db['keys'][slot]:08x}",
        "original_array_value_u32":f"{db['values'][slot]:08x}",
        "has_M25_verified_source_to_texture_link":bool(source),
        "source_oid":source["source_oid"] if source else f"{db['values'][slot]:08x}",
        "texture_oid":source["target_texture_oid"] if source else None,
        "original_texinfo_names":source["original_texture_name_variants"].split(";") if source else [],
        "original_g1t_hash":source["g1t_hash"] if source else None,
        "original_texinfo_hash":source["texinfo_hash"] if source else None,
        "source_qualified_png_paths":source["original_png_candidates"].split(";") if source else [],
        "native_game_species_id_verified":False,
        "runtime_villager_id_to_source_oid_verified":False,
    }
    return data

def by_name(db,name):
    family,num,variant=parse_name(name)
    model=db["constants"].get((family,variant))
    if model is None:
        return {"name":name,"status":"UNMODELED_VARIANT_OR_TEXTURE_NAME",
                "native_game_species_id_verified":False}
    a,b=FAMILIES[family]["shifts"]
    token=h31(reverse_four(num))
    ck,cv=int(model["constant_key"],16),int(model["constant_value"],16)
    key=(token*power31(a)+ck)&KEY_MASK
    value=(token*power31(b)+cv)&KEY_MASK
    slot=db["key_to_slot"].get(key)
    answer={
        "requested_original_texture_name":name,
        "original_family":family,
        "original_variant":variant,
        "reverse_four_decimal_component":reverse_four(num),
        "model_evidence_grade":model["evidence_grade"],
        "predicted_original_key_hash":f"{key:08x}",
        "predicted_source_oid":f"{value:08x}",
        "key_present_in_original_3543_array":slot is not None,
        "native_game_species_id_verified":False,
    }
    if slot is None:
        answer.update(status="NO_EXACT_ORIGINAL_KIDS_KEY_IN_THIS_3543_ARRAY")
        return answer
    original=slot_info(db,slot)
    exact=original["original_array_value_u32"]==f"{value:08x}"
    source_name_in_alias=name in original["original_texinfo_names"]
    alias_hits=[]
    for idx,source in db["sources"].items():
        if name in source["original_texture_name_variants"].split(";"):
            alias_hits.append({"slot":idx,"source_oid":source["source_oid"],
                               "texture_oid":source["target_texture_oid"]})
    answer.update(
        original=original,
        source_oid_and_key_both_match=exact,
        requested_texinfo_name_is_native_source_alias=source_name_in_alias,
        alternative_native_texture_name_alias_sources=alias_hits,
        status=("EXACT_ORIGINAL_SOURCE_NAME_AND_OID" if exact and source_name_in_alias
                else "HASH_KEY_MATCH_BUT_ORIGINAL_SOURCE_OR_NAME_NOT_VERIFIED"),
    )
    return answer

def validate_all(db):
    proof=read_csv(PROOF)
    if len(proof)!=626:raise ValueError("M27 model set changed")
    got=0
    fails=[]
    for x in proof:
        ans=by_name(db,x["original_name"])
        if not (ans["status"]=="EXACT_ORIGINAL_SOURCE_NAME_AND_OID" and
                ans["original"]["native_original_array_index"]==int(x["original_slot"]) and
                ans["original"]["source_oid"]==x["original_source_oid"] and
                ans["original"]["original_key_u32"]==x["original_key_hash"]):
            fails.append({"name":x["original_name"],"actual":ans.get("status")})
        else:got+=1
    if fails:raise ValueError(f"Source model failed {len(fails)} original M27 records: {fails[:5]}")
    return {"original_source_NSO_version":"2.0.1",
            "matched_named_original_KIDS_icon_records":got,
            "all_records_validated":got==626,
            "native_game_species_id_verified":False,
            "native_runtime_ID_to_KIDS_source_oid_verified":False}

def selftest():
    assert parse_name("icon_poke_0043_00_00_00")==("normal","0043","00_00_00")
    assert parse_name("icon_poke_uni_0910_00_00_00_nh")==("uni","0910","00_00_00_nh")
    assert h31(reverse_four("0043"))==0x17F821
    print("PASS original resource naming and numeric-reverse hash input")
def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group()
    g.add_argument("--name",type=str)
    g.add_argument("--slot",type=int)
    g.add_argument("--verify-all",action="store_true")
    g.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest();return
    if not (args.name or args.slot is not None or args.verify_all):
        p.error("Use --name, --slot, --verify-all or --self-test")
    db=load()
    result=(by_name(db,args.name) if args.name else
            slot_info(db,args.slot) if args.slot is not None else
            validate_all(db))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
