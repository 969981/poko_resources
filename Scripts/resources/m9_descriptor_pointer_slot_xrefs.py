#!/usr/bin/env python3
"""M9.9: inspect exact .data pointer slots and possible ARM64 readers.

Static references to descriptor callbacks are not proof of runtime property
lookups or text foreign keys. Source NSO/slot bytes are checked strictly.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_rnk_exefs_xrefs import find_references

EXPECTED_SHA = "8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"


def pointer_slots(entry_graph):
    slots={}
    for row in entry_graph["xrefs"]:
        if row["kind"]!="U64_LITERAL_ADDRESS_CANDIDATE" or row["section"]!="data":
            continue
        h=row["hash"]
        slots.setdefault(h,[]).append((int(row["site_pc"]),int(row["entry_pc"])))
    names={row["hash"] for row in entry_graph["report"]["entry_functions"]}
    if set(slots)!=names or any(len(v)!=1 for v in slots.values()):
        raise ValueError("Incomplete/ambiguous M9.7 .data entry pointer evidence")
    return {name:matches[0] for name,matches in slots.items()}


def analyze(main_blob,prior):
    sha=hashlib.sha256(main_blob).hexdigest()
    if sha!=EXPECTED_SHA or prior["report"]["original_exefs_sha256"]!=sha:
        raise ValueError("Original ExeFS provenance drift")
    kind,segments=get_sections(main_blob)
    if kind!="NSO0":
        raise ValueError("Not NSO0")
    text=next(x for x in segments if x["name"]=="text")
    data=next(x for x in segments if x["name"]=="data")
    slots=pointer_slots(prior)
    neighbors=[]
    for key,(site,target) in slots.items():
        p=site-data["mem_offset"]
        if p<0 or p+8>len(data["data"]):
            raise ValueError("Function pointer outside data segment")
        if struct.unpack_from("<Q",data["data"],p)[0]!=target:
            raise ValueError("Original static function pointer changed")
        start=max(0,(p-64)//8*8)
        end=min(len(data["data"]), (p+72)//8*8)
        neighbors.append({
            "hash":key,"slot_va":site,"entry_pc":target,
            "surrounding_qwords":[
                {"va":data["mem_offset"]+i,
                 "value":f"0x{struct.unpack_from('<Q',data['data'],i)[0]:016x}",
                 "is_entry":i==p}
                for i in range(start,end,8) if i+8<=len(data["data"])
            ]})
    refs=find_references(text["data"],text["mem_offset"],
                         {slot:int(name,16) for name,(slot,_) in slots.items()})
    for item in refs:
        item["runtime_descriptor_reader_verified"]=False
        item["script_m7_text_fk_verified"]=False
        item["evidence_grade"]="STATIC_CODE_REF_TO_FUNCTION_POINTER_SLOT_ONLY"
    return {
        "status":"M9_STATIC_DESCRIPTOR_POINTER_SLOT_REFS_ONLY",
        "source_exefs_sha256":sha,
        "static_pointer_slots":neighbors,
        "code_reference_candidates":len(refs),
        "verified_runtime_descriptor_reader":0,
        "verified_native_property_getter":0,
        "verified_scene_quest_building_text_fk":0,
        "limitations":[
            "ADRP plus adjacent LDR/ADD only identifies a possible pointer-slot access.",
            "Instruction window matching does not prove the loaded function pointer was invoked.",
            "Even a proven callback invocation is not a KIDSOBJDB getter or a script-to-M7 FK.",
        ],
    }, refs


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--m9-entry-graph",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    args=p.parse_args()
    report,refs=analyze(args.main.read_bytes(),
                        json.loads(args.m9_entry_graph.read_text(encoding="utf-8")))
    args.dest.mkdir(parents=True,exist_ok=True)
    (args.dest/"exefs_descriptor_pointer_slot_xrefs.json").write_text(
        json.dumps({"report":report,"code_xrefs":refs},ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    with (args.dest/"exefs_descriptor_pointer_slot_xrefs.csv").open("w",newline="",encoding="utf-8") as f:
        cols=["property_hash","literal_virtual_offset","adrp_pc","consumer_pc",
              "distance_instructions","instruction_kind","evidence",
              "evidence_grade","runtime_descriptor_reader_verified","script_m7_text_fk_verified"]
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for r in refs:
            w.writerow({k:r[k] for k in cols})
    print(json.dumps({k:v for k,v in report.items() if k!="static_pointer_slots"},
                     indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
