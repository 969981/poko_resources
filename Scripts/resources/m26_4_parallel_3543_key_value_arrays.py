#!/usr/bin/env python3
"""M26.4: examine original KIDS twin 3543-element u32 arrays as aligned pairs.

Original class 0x9D1AFA46 enumerates fields 0xE88C8D60 and 0x34CBB458
using method main+0xDD1B48. Both typed native arrays contain exactly
3543 u32s, adjacent in root_019167 KIDSOBJDB.

Do not claim the first field is a game species ID or name hash until
the original consumer or a validated hash algorithm proves that semantics.
"""
from __future__ import annotations
import argparse
import binascii
import csv
import hashlib
import json
import struct
from collections import Counter,defaultdict
from pathlib import Path
from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

R=Path("UnPack/2.0.1/Resources")
OUT=R/"Villagers/Native_2.0.1/M26"
SRC=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native/root_019167_50ae86ef.kidsobjdb")
SHA="86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541"
ICON=R/"Pokemon/NativeRecoveryM25/m25_8_complete_native_629_kids_icon_source_index.csv"
OWNER=0xB4A1803B
TYPE=0x9D1AFA46
COUNT=3543
SCALAR=0x2F610FEA
KEY=0xE88C8D60
VALUE=0x34CBB458
MAIN_SLOTS=range(429,1057)
HEADERS=("native_array_index","original_key_u32","original_value_u32",
         "original_key_field_offset","original_value_field_offset",
         "icon_source_oid_matches_original_registry","M25_source_oid",
         "M25_texture_oid","M25_native_texture_names",
         "game_species_id_identity_proven","original_name_hash_algorithm_proven")

def read(p):
    with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))

def fnv32(b,variant="fnv1a"):
    v=0x811c9dc5
    for byte in b:
        if variant=="fnv1a":
            v=((v^byte)*0x01000193)&0xffffffff
        else:
            v=((v*0x01000193)^byte)&0xffffffff
    return v

def djb2(b):
    v=5381
    for byte in b:v=((v*33)+byte)&0xffffffff
    return v

def sdbm(b):
    v=0
    for byte in b:v=(byte+(v<<6)+(v<<16)-v)&0xffffffff
    return v

HASH_ALGOS={
    "CRC32":lambda b:binascii.crc32(b)&0xffffffff,
    "FNV1A":lambda b:fnv32(b,"fnv1a"),
    "FNV1":lambda b:fnv32(b,"fnv1"),
    "DJB2":djb2,
    "SDBM":sdbm,
}
CONVENTIONS={
    "ASCII_EXACT":lambda x:x.encode("ascii"),
    "ASCII_LOWER":lambda x:x.lower().encode("ascii"),
    "ASCII_UPPER":lambda x:x.upper().encode("ascii"),
    "UTF16LE_EXACT":lambda x:x.encode("utf-16le"),
    "ASCII_WITH_PNG":lambda x:(x+".png").encode("ascii"),
    "ASCII_WITH_TEXINFO":lambda x:(x+".texinfo").encode("ascii"),
}

def run():
    blob=SRC.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=SHA:
        raise ValueError("Pinned original KIDS native byte source changed")
    _,nodes=parse_kids(blob)
    obj=nodes.get(OWNER)
    if obj is None or obj["type"]!=TYPE:
        raise ValueError("Original KIDS class and root array holder changed")
    k=obj["fields"].get(KEY);v=obj["fields"].get(VALUE);scalar=obj["fields"].get(SCALAR)
    if (not k or not v or not scalar or k["count"]!=COUNT or v["count"]!=COUNT
        or scalar["count"]!=1 or k["kind"] not in (4,5) or v["kind"] not in (4,5)
        or v["offset"]!=k["offset"]+4*COUNT):
        raise ValueError("Twin 3543-element native table structure invalid")
    kdata=struct.unpack_from("<"+"I"*COUNT,blob,k["offset"])
    vdata=struct.unpack_from("<"+"I"*COUNT,blob,v["offset"])
    scalar_value=struct.unpack_from("<I",blob,scalar["offset"])[0]
    original=read(ICON)
    if len(original)!=629:raise ValueError("M25.8 complete native index absent")
    byslot={}
    for row in original:
        if row["original_owner_oid"]!="b4a1803b":continue
        idx=int(row["original_array_index"])
        if idx in byslot:raise ValueError("M25 KIDS source duplicate original array slot")
        byslot[idx]=row
    if set(byslot)!=set(MAIN_SLOTS):
        raise ValueError("Original 628 Pokemon source slots not covered by M25")
    table=[]
    for idx,(key,value) in enumerate(zip(kdata,vdata)):
        row=byslot.get(idx)
        if row and value!=int(row["source_oid"],16):
            raise ValueError(f"Original array value/source OID mismatch at {idx}")
        table.append({
            "native_array_index":idx,
            "original_key_u32":f"{key:08x}",
            "original_value_u32":f"{value:08x}",
            "original_key_field_offset":k["offset"]+4*idx,
            "original_value_field_offset":v["offset"]+4*idx,
            "icon_source_oid_matches_original_registry":int(bool(row)),
            "M25_source_oid":row["source_oid"] if row else "",
            "M25_texture_oid":row["target_texture_oid"] if row else "",
            "M25_native_texture_names":row["original_texture_name_variants"] if row else "",
            "game_species_id_identity_proven":"",
            "original_name_hash_algorithm_proven":"",
        })
    # Test numerous common hash algorithms as *hypotheses*. A best score of
    # zero explicitly means no match; never use a guessed algorithm to label
    # or fill KIDS hashes without original program consumer confirmation.
    counts=Counter()
    testing=0
    matched_samples=defaultdict(list)
    for idx,orig in byslot.items():
        for name in set(orig["original_texture_name_variants"].split(";")):
            for conv,makebytes in CONVENTIONS.items():
                try:b=makebytes(name)
                except UnicodeEncodeError:continue
                for algorithm,fun in HASH_ALGOS.items():
                    testing+=1
                    if fun(b)==kdata[idx]:
                        label=algorithm+"__"+conv
                        counts[label]+=1
                        if len(matched_samples[label])<12:
                            matched_samples[label].append({"slot":idx,"name":name,
                                                           "original_key":f"{kdata[idx]:08x}"})
    summary={
        "game_version":"2.0.1","original_source_sha256":SHA,
        "original_class_type_hash":f"0x{TYPE:08x}",
        "original_owner_oid":f"{OWNER:08x}",
        "original_scalar_field_hash":f"{SCALAR:08x}",
        "original_scalar_value":scalar_value,
        "original_first_array_hash":f"{KEY:08x}",
        "original_second_array_hash":f"{VALUE:08x}",
        "original_parallel_array_element_count":COUNT,
        "first_array_data_start_byte_offset":k["offset"],
        "second_array_data_start_byte_offset":v["offset"],
        "parallel_arrays_exactly_adjacent":v["offset"]==k["offset"]+4*COUNT,
        "verified_M25_native_icon_source_OID_pairs":len(byslot),
        "first_array_distinct_value_count":len(set(kdata)),
        "first_array_zero_count":sum(not x for x in kdata),
        "first_array_small_numeric_value_at_most_1000":sum(x<=1000 for x in kdata),
        "second_array_distinct_value_count":len(set(vdata)),
        "second_array_zero_count":sum(not x for x in vdata),
        "hash_candidate_comparisons":testing,
        "hypothesized_original_name_hash_exact_match_counts":dict(counts.most_common()),
        "hypothesized_name_hash_match_examples":dict(matched_samples),
        "native_game_species_id_to_array_index_proven":False,
        "original_first_array_semantic_identity_proven":False,
        "warning":"The two same-size original arrays are aligned, but the first array may be resource key hashes or another opaque field; game species IDs and hashing methods must be proven by original consumers.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"m26_4_original_3543_parallel_key_value_pairs.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=HEADERS);w.writeheader();w.writerows(table)
    (OUT/"m26_4_parallel_arrays_analysis.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert 3543*4==14172
    assert len(MAIN_SLOTS)==628
    assert fnv32(b"abc")==0x1A47E90B
    assert binascii.crc32(b"123456789")==0xCBF43926
    print("PASS parallel arrays dimensions and hash comparison selftests")
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test",action="store_true")
    a=ap.parse_args()
    if a.self_test:selftest()
    else:run()
if __name__=="__main__":main()
