#!/usr/bin/env python3
"""M9.18: exact callback-entry data pointers for owner+0x28 constructor/cleanup.

M9.17 proved instruction sequences and known class slot-0 vptr. Find the
two *specific* callback function entry PCs in original NSO non-text
sections and report table neighborhoods. This is NOT a generic BLR scan,
and same-neighborhood addresses do not by themselves establish dynamic
owner identity or registration semantics.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ENTRIES={
    "owner_cleanup_callback":0xD58E34,
    "owner_constructor_callback":0xD590E0,
}
ALTERNATE={
    "owner_cleanup_body":0xD58E38,
    "owner_constructor_body":0xD590E4,
}
WINDOW=0x100


def find_exact_qwords(section,targets):
    result=[]
    data=section["data"]
    base=section["mem_offset"]
    for key,number in targets.items():
        target=struct.pack("<Q",number)
        cursor=0
        while True:
            off=data.find(target,cursor)
            if off<0:break
            cursor=off+1
            if off%8:continue
            result.append({
                "function":key,
                "callback_entry_pc":number,
                "section":section["name"],
                "pointer_data_va":base+off,
                "pointer_data_file_offset":section["file_offset"]+off,
                "verified_exact_qword":True,
            })
    return result


def neighborhood(section,address,radius=WINDOW):
    base=section["mem_offset"]
    data=section["data"]
    off=address-base
    lo=max(0,(off-radius)//8*8)
    hi=min(len(data),(off+radius+8)//8*8)
    return [
        {"data_va":base+j,
         "qword":f"0x{struct.unpack_from('<Q',data,j)[0]:016x}",
         "distance_from_pointer":j-off}
        for j in range(lo,hi,8) if j+8<=len(data)
    ]


def analyze(blob,prior):
    sha=hashlib.sha256(blob).hexdigest()
    r=prior["report"]
    if sha!=SHA or r["original_exefs_sha256"]!=sha:
        raise ValueError("Wrong original ExeFS / M9.17 source")
    if (r["actual_indirect_callsite_pc_verified"]!=0xD58F10 or
        r["resolved_vtable_slot0_target_if_object_vptr_unmodified"]!=0xD593CC):
        raise ValueError("M9.17 concrete virtual slot0 proof missing")
    kind,parts=get_sections(blob)
    if kind!="NSO0":raise ValueError("Original NSO required")
    nontext=[x for x in parts if x["name"]!="text"]
    hits=[]
    target_map={**ENTRIES,**ALTERNATE}
    for section in nontext:
        hits.extend(find_exact_qwords(section,target_map))
    for hit in hits:
        part=next(x for x in nontext if x["name"]==hit["section"])
        hit["context_qwords"]=neighborhood(part,hit["pointer_data_va"])
    pairs=[]
    for a in hits:
        if a["function"]!="owner_cleanup_callback":continue
        for b in hits:
            if (b["function"]!="owner_constructor_callback" or
                a["section"]!=b["section"]):
                continue
            delta=b["pointer_data_va"]-a["pointer_data_va"]
            if abs(delta)>0x300:continue
            pairs.append({
                "cleanup_slot_va":a["pointer_data_va"],
                "constructor_slot_va":b["pointer_data_va"],
                "same_nontext_section":True,
                "pointer_byte_distance":delta,
                "same_static_registry_proven":False,
                "same_runtime_owner_proven":False,
                "evidence_grade":"TWO_FUNCTION_PTR_QWORDS_IN_STATIC_NEIGHBORHOOD_ONLY",
            })
    report={
        "status":"M9_SPECIFIC_OWNER_CALLBACK_POINTER_TABLE_XREFS",
        "source_exefs_sha256":sha,
        "exact_entry_probes":ENTRIES,
        "alternate_body_probes":ALTERNATE,
        "native_qword_pointer_hits":len(hits),
        "strict_function_entry_hits":sum(h["function"] in ENTRIES for h in hits),
        "nearby_two_entry_pointer_pairs":len(pairs),
        "verified_original_slot0_callsite_pc":0xD58F10,
        "same_runtime_owner_type_proven":False,
        "registered_dispatch_consumer_proven":False,
        "original_descriptor_callback_slot0x38_actual_dispatch_proven":False,
        "native_RNK_sources_loaded":0,
        "script_to_M7_foreign_keys":0,
        "limitations":[
            "Exact native pointer bytes and relative proximity are data provenance, not a native caller argument flow.",
            "Prologue PCs come from M9.16 native PACIBSP/function-frame patterns; a code pointer may point to a thunk instead.",
            "Even a shared callback table cannot prove two method invocations receive the same runtime x3 argument.",
            "Indirect slot0 method is distinct from known descriptor slot0x38.",
        ],
    }
    return {"report":report,"data_pointer_xrefs":hits,"same_table_neighborhood_candidates":pairs}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--m9-17",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    a=p.parse_args()
    result=analyze(a.main.read_bytes(),json.loads(a.m9_17.read_text(encoding="utf-8")))
    a.dest.mkdir(parents=True,exist_ok=True)
    (a.dest/"exefs_owner_two_callback_pointer_tables.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result["report"],ensure_ascii=False,indent=2))


if __name__=="__main__":main()
