#!/usr/bin/env python3
"""Crosswalk native 2.0.1 item-group bytes with one public material list.

48 raw +0x26=16 IDs are original-game byte facts; the external 50-item list is
secondary classification context only, NOT the original game enum definition.
"""
from __future__ import annotations
import argparse,csv,hashlib,json,struct
from pathlib import Path

SRC=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
CATALOG=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/native_item_catalog.csv")
DEST=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1")
ORIGINAL_SHA="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
REFERENCE="https://pokopia.pokemonhubs.com/items/"
# Hand-reviewed secondary-public material list: 50 distinct named items.
# Native English/Chinese source names are always generated from game bytes.
# This ID list is NOT a native ID-to-type table and can be version-dependent.
SECONDARY_PUBLIC_IDS=(
    101,102,105,106,107,108,109,110,111,112,113,114,115,116,117,118,
    119,120,121,123,124,125,126,129,130,221,222,223,224,225,226,227,228,
    290,311,323,404,407,435,436,437,520,532,565,1206,1291,1419,1482,1801,3994,
)
FIELDS=("item_id","record_file_offset","raw_item_kind_candidate_u8_0x26",
        "raw_secondary_group_u8_0x39","raw_another_group_u8_0x3A",
        "native_name_index_u16_0x22","jp","en","de","es","fr","it","ko","zhs","zht",
        "secondary_public_material_list","evidence","native_enum_name_verified",
        "native_983_consumer_link_verified")

def build(blob,catalog):
    if hashlib.sha256(blob).hexdigest()!=ORIGINAL_SHA:
        raise ValueError("Native item table source SHA does not match original version 2.0.1")
    if len(blob)!=64+4600*68 or struct.unpack_from("<II",blob,0)!=(4600,3):
        raise ValueError("Original 00983.bin count/version/68-byte record mismatch")
    if len(catalog)!=4600 or any(int(x["item_id"])!=i for i,x in enumerate(catalog)):
        raise ValueError("Native nine-language item catalogue must have exact 4600 ID slots")
    if len(set(SECONDARY_PUBLIC_IDS))!=len(SECONDARY_PUBLIC_IDS)==50:
        raise ValueError("Secondary material-list review must contain exactly 50 unique IDs")
    rows=[]
    for i in range(1,4600):
        pos=64+i*68
        name_index=struct.unpack_from("<H",blob,pos+0x22)[0]
        native=catalog[i]
        if name_index!=int(native["native_name_index"]):
            raise ValueError(f"Native 00983 NameIndex disagrees with nine-language table: {i}")
        type_raw=blob[pos+0x26]
        external=i in SECONDARY_PUBLIC_IDS
        if type_raw!=16 and not external:
            continue
        rows.append({
            "item_id":i,"record_file_offset":pos,
            "raw_item_kind_candidate_u8_0x26":type_raw,
            "raw_secondary_group_u8_0x39":blob[pos+0x39],
            "raw_another_group_u8_0x3A":blob[pos+0x3a],
            "native_name_index_u16_0x22":name_index,
            **{k:native[k] for k in ("jp","en","de","es","fr","it","ko","zhs","zht")},
            "secondary_public_material_list":int(external),
            "evidence":"NATIVE_2_0_1_RECORD_RAW_GROUP_PLUS_PUBLIC_REFERENCE"
                         if external else "NATIVE_2_0_1_RECORD_RAW_GROUP_ONLY",
            "native_enum_name_verified":0,
            "native_983_consumer_link_verified":0,
        })
    native16=[r for r in rows if r["raw_item_kind_candidate_u8_0x26"]==16]
    common=[r for r in native16 if r["secondary_public_material_list"]==1]
    outside=[r for r in rows if r["secondary_public_material_list"]==1 and
             r["raw_item_kind_candidate_u8_0x26"]!=16]
    if len(native16)!=48 or len(common)!=48 or len(outside)!=2:
        raise ValueError(f"Expected native group=48, common=48, public-only=2; got {len(native16)}/{len(common)}/{len(outside)}")
    if {r["item_id"]:r["raw_item_kind_candidate_u8_0x26"] for r in outside}!={532:15,1291:10}:
        raise ValueError("Secondary material exceptions no longer match native source bytes")
    stats={
        "status":"NATIVE_RAW_GROUP_AND_SECONDARY_REFERENCE_MATCH__NATIVE_ENUM_NOT_PROVEN",
        "game_version":"2.0.1","original_record_sha256":ORIGINAL_SHA,
        "native_kind_offset_u8":38,"native_raw_kind_value":16,
        "native_raw_kind_16_item_ids":48,
        "secondary_reference_url":REFERENCE,
        "secondary_reference_material_count":50,
        "reference_intersection_with_native_kind_16":48,
        "reference_outside_native_kind_16":[
             {"item_id":r["item_id"],"en":r["en"],"zhs":r["zhs"],
              "raw_kind":r["raw_item_kind_candidate_u8_0x26"]} for r in outside],
        "official_native_enum_name_verified":False,
        "game_original_item_983_loader_connected_to_consumer":False,
        "explanation":"Independent public guide classification is not an official or native field enum, even if all 48 group-16 items match."
    }
    return rows,stats

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=SRC)
    p.add_argument("--catalog",type=Path,default=CATALOG)
    p.add_argument("--dest",type=Path,default=DEST)
    args=p.parse_args()
    with args.catalog.open(encoding="utf-8-sig",newline="") as f:
        catalog=list(csv.DictReader(f))
    rows,stats=build(args.source.read_bytes(),catalog)
    args.dest.mkdir(parents=True,exist_ok=True)
    with (args.dest/"native_material_candidate_crosswalk.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
    (args.dest/"native_material_candidate_summary.json").write_text(
        json.dumps(stats,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(stats,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
