#!/usr/bin/env python3
"""M9.14: find AArch64 load-vptr / load-slot-0x38 / BLR callsite patterns.

M9.12 proves one original vptr carries the descriptor enum callback at
offset 0x38. This scan finds GENERIC indirect dispatch shapes for that
slot offset; the target object type/callee remains unknown without
object identity or runtime call evidence.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
OFFSET=0x38
MAX_EXAMPLES=700


def u32(data,offset):
    return struct.unpack_from("<I",data,offset)[0]


def ldr64(word):
    if word&0xffc00000 != 0xf9400000:
        return None
    return ((word>>5)&31,word&31,((word>>10)&0xfff)*8)


def branch_indirect(word):
    if word&0xfffffc1f == 0xd63f0000:
        return ("BLR",(word>>5)&31)
    if word&0xfffffc1f == 0xd61f0000:
        return ("BR",(word>>5)&31)
    return None


def scan_dispatch_patterns(code,base,max_examples=MAX_EXAMPLES):
    stats=collections.Counter()
    examples=[]
    for pos in range(4,len(code)-27,4):
        mid=ldr64(u32(code,pos))
        if mid is None or mid[2]!=OFFSET:
            continue
        stats["all_ldr64_slot_0x38"]+=1
        previous=ldr64(u32(code,pos-4))
        follows=[]
        for next_delta in (4,8,12,16,20,24):
            call=branch_indirect(u32(code,pos+next_delta))
            if call and call[1]==mid[1]:
                follows.append((next_delta,call[0]))
        if not follows:continue
        stats["slot_load_followed_by_same_reg_indirect_branch"]+=1
        prior_is_vptr=(previous is not None and previous[1]==mid[0] and previous[2]==0)
        if prior_is_vptr:
            stats["adjacent_object_vptr_load"]+=1
        for next_delta,opcode in follows:
            direct=prior_is_vptr and next_delta==4 and opcode=="BLR"
            label=("ADJACENT_LDR_VPTR_LDR_SLOT_BLR_SHAPE" if direct else
                   "NONADJACENT_OR_UNTYPED_VIRTUAL_SLOT_CALL_CANDIDATE")
            stats[label]+=1
            if len(examples)<max_examples:
                examples.append({
                    "slot_load_pc":base+pos,
                    "optional_prior_vptr_load_pc":base+pos-4 if prior_is_vptr else None,
                    "indirect_branch_pc":base+pos+next_delta,
                    "indirect_branch_op":opcode,
                    "slot_offset":OFFSET,
                    "slot_base_register":f"x{mid[0]}",
                    "loaded_callback_register":f"x{mid[1]}",
                    "vptr_source_object_register":f"x{previous[0]}" if prior_is_vptr else None,
                    "raw_words_hex":[
                        f"{u32(code,pos-4):08x}",
                        f"{u32(code,pos):08x}",
                        f"{u32(code,pos+next_delta):08x}",
                    ],
                    "evidence_grade":label,
                    "target_class_or_vtable_proven":False,
                    "specific_descriptor_callback_proven":False,
                    "script_text_fk_verified":False,
                })
    return dict(stats),examples


def analyze(main,prior):
    sha=hashlib.sha256(main).hexdigest()
    if sha!=SHA or prior["report"].get("original_exefs_sha256")!=sha:
        raise ValueError("Wrong original ExeFS or M9.12 vptr evidence")
    verified=[r for r in prior["verified_stores"] if r.get("verified_callback_pointer_at_vptr_offset")]
    if len(verified)!=1 or verified[0]["vtable_callback_offset"]!=OFFSET or verified[0]["table_callback_pc"]!=0xd59420:
        raise ValueError("M9.12 original callback slot unverified")
    kind,sections=get_sections(main)
    if kind!="NSO0": raise ValueError("Expected NSO0")
    section=next(x for x in sections if x["name"]=="text")
    count,candidates=scan_dispatch_patterns(section["data"],section["mem_offset"])
    report={
        "status":"M9_GENERIC_INDIRECT_SLOT_0X38_DISPATCH_TRIAGE",
        "original_exefs_sha256":sha,
        "known_original_vtable_address":verified[0]["written_pointer"],
        "known_original_slot_offset":OFFSET,
        "known_descriptor_callback":verified[0]["table_callback_pc"],
        "scan_counts":count,
        "candidate_examples_saved":len(candidates),
        "specific_runtime_object_dispatches_verified":0,
        "KIDSOBJDB_getter_callers_verified":0,
        "new_script_scene_quest_building_text_foreign_keys":0,
        "warnings":[
            "These are original ARM64 dispatch instruction shapes, not instances of the proven descriptor class.",
            "An adjacent LDR-LDR-BLR triplet proves generic indirect dispatch structure only.",
            "Nonadjacent forms may include register clobber or control-flow divergence.",
            "No fetched callback has been shown consuming KIDSOBJDB properties or M7 IDs.",
        ],
    }
    return report,candidates


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--verified-vptr",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    args=p.parse_args()
    report,examples=analyze(args.main.read_bytes(),
                            json.loads(args.verified_vptr.read_text(encoding="utf-8")))
    args.dest.mkdir(parents=True,exist_ok=True)
    (args.dest/"exefs_virtual_slot_0x38_dispatch_candidates.json").write_text(
        json.dumps({"report":report,"examples":examples},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":main()
