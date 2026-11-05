#!/usr/bin/env python3
"""M31.2: recover ALL three original StaticScreenLayoutTextures field labels.

Source:
  original main ExeFS SHA256 pinned (2.0.1)
  registered type hash 0x79991E79, class label StaticScreenLayoutTextures
  class property method main+0xCE854C:
      ldr w11,[x8,w3,sxtw #2]  from rodata main+0x2830C90
      ldr x12,[x9,w3,sxtw #3]  from data   main+0x3330928
  static representative typed original KIDS Source OID 0x06AB845F,
  target texture OID 0xC1A6D60C under original property 0x2856A1B3.

Field metadata is class schema; native resource lookup and real game ID
are NOT proven by these labels or the representative Source OID.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import MAIN,SHA_MAIN,arm64_window
from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M31")
ORIGINAL_KIDS=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native/root_019167_50ae86ef.kidsobjdb")
KIDS_SHA="86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541"
TYPE=0x79991E79
SOURCE=0x06AB845F
TARGET=0xC1A6D60C
TEXTURE_FIELD_HASH=0x2856A1B3
NAME="StaticScreenLayoutTextures"
NAMERO=0x279B44D
ROHASH=0x2830C90
DATA_LABEL=0x3330928
METHOD=0xCE854C
COUNT=3

def span(parts,pc,n):
    for p in parts:
        k=pc-p["mem_offset"]
        if 0<=k and k+n<=len(p["data"]):
            return p["name"],bytes(p["data"][k:k+n])
    return "",None

def read_text(parts,ptr):
    sec,data=span(parts,ptr,360)
    if sec!="rodata":raise ValueError(f"Native class label pointer is not rodata: {ptr:x}")
    nul=data.find(b"\0")
    if not 1<=nul<=180:raise ValueError("Native property label not bounded/NUL terminated")
    return data[:nul].decode("utf-8"),data[:nul].hex()

def run():
    main=MAIN.read_bytes()
    if hashlib.sha256(main).hexdigest()!=SHA_MAIN:
        raise ValueError("Original 2.0.1 ExeFS differs")
    kind,parts=get_sections(main)
    if kind!="NSO0":raise ValueError("Original NSO0 needed")
    sec,name=span(parts,NAMERO,len(NAME)+1)
    if sec!="rodata" or name!=NAME.encode()+b"\0":
        raise ValueError("Original class label no longer matches")
    x,rawhash=span(parts,ROHASH,COUNT*4)
    y,rawptr=span(parts,DATA_LABEL,COUNT*8)
    if x!="rodata" or y!="data":
        raise ValueError("Original field descriptor hash/pointer cells changed")
    hashes=struct.unpack("<3I",rawhash)
    pointers=struct.unpack("<3Q",rawptr)
    text=next(p for p in parts if p["name"]=="text")
    code=arm64_window(text["data"],text["mem_offset"],METHOD,0,0x80)
    bypc={int(a["pc"],16):a["asm"] for a in code}
    if not ("[x8, w3, sxtw #2]" in bypc.get(0xCE856C,"") and
            "[x9, w3, sxtw #3]" in bypc.get(0xCE8570,"")):
        raise ValueError("Original StaticScreenLayoutTextures field descriptor read instructions changed")
    kids=ORIGINAL_KIDS.read_bytes()
    if hashlib.sha256(kids).hexdigest()!=KIDS_SHA:
        raise ValueError("Original KIDSOBJDB source changed")
    _,objs=parse_kids(kids)
    node=objs.get(SOURCE)
    if node is None or node["type"]!=TYPE:
        raise ValueError("M25 original typed StaticScreenLayoutTextures Source OID disappeared")
    field=node["fields"].get(TEXTURE_FIELD_HASH)
    if not field or field["count"]!=1:
        raise ValueError("M25 original source→texture typed field missing")
    if struct.unpack_from("<I",kids,field["offset"])[0]!=TARGET:
        raise ValueError("M25 original source→texture OID value differs")
    records=[]
    for n,(h,p) in enumerate(zip(hashes,pointers)):
        label,raw=read_text(parts,p)
        have=node["fields"].get(h)
        records.append({
            "descriptor_index":n,
            "original_type_hash":f"{TYPE:08x}",
            "original_property_hash":f"{h:08x}",
            "original_property_name_utf8":label,
            "original_property_name_hex":raw,
            "original_property_name_rodata_va":hex(p),
            "original_field_label_data_pointer_cell":hex(DATA_LABEL+n*8),
            "original_KIDS_sample_object_has_field":have is not None,
            "original_sample_field_kind":have["kind"] if have else None,
            "original_sample_field_count":have["count"] if have else None,
            "original_sample_field_data_offset":have["offset"] if have else None,
            "source_OID_to_texture_OID_field":h==TEXTURE_FIELD_HASH,
            "native_runtime_object_lookup_consumer_proven":False,
            "game_species_ID_binding_proven":False,
        })
    if TEXTURE_FIELD_HASH not in hashes:raise ValueError("M25 typed texture property not among native class schema")
    summary={
        "game_version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "original_kids_objdb_sha256":KIDS_SHA,
        "native_class_original_name":NAME,
        "class_type_hash":f"{TYPE:08x}",
        "native_property_descriptor_count":COUNT,
        "all_original_property_labels_read_from_rodata":True,
        "original_property_hash_list":[f"{h:08x}" for h in hashes],
        "original_property_name_list":[x["original_property_name_utf8"] for x in records],
        "representative_native_source_OID":f"{SOURCE:08x}",
        "representative_native_texture_OID":f"{TARGET:08x}",
        "representative_property_is_original_typed_u32_OID":True,
        "runtime_texture_selection_consumer_confirmed":False,
        "real_pokemon_species_or_form_ID_confirmed":False,
        "warning":"Native property schema and representative typed Source OID->Texture OID are source-backed; no gameplay species/form-to-asset query edge has been recovered.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m31_2_original_StaticScreenLayoutTextures_3_field_labels.json").write_text(
        json.dumps({"summary":summary,"native_original_descriptor_records":records,
                    "property_method_original_asm":code},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m31_2_static_texture_schema_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:
        assert ROHASH==0x2830C90 and DATA_LABEL==0x3330928 and COUNT==3
        print("PASS 2.0.1 original StaticScreenLayoutTextures descriptor address invariants")
    else:run()
