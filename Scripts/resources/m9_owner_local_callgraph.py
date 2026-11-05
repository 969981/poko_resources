#!/usr/bin/env python3
"""M9.16: x19 owner provenance and *local* calls around verified object escape.

Constrain the probe to the code containing M9.15 x23 -> [x19+0x28].
Use exact original NSO SHA and M9.15 source PCs; enumerate x19
definitions, frame prologue candidates, direct BL incoming references
and actual +0x28 loads in that neighborhood. A nearby prologue is
not independently proof of a function boundary or object identity.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_owner_object_escape import ldrx

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ROI_BEGIN=0xD57C00
ROI_END=0xD59C00
VSTORE=0xD591C8
OWNER_STORE=0xD59274
MAX_TARGETS=2500

def u32(data,off):return struct.unpack_from("<I",data,off)[0]

def decode_bl_target(word,pc):
    if word&0xfc000000!=0x94000000:return None
    imm=word&0x3ffffff
    if imm&(1<<25):imm-=1<<26
    return pc+(imm<<2)

def incoming_bl(code,base,start,end):
    counter=collections.Counter()
    samples=collections.defaultdict(list)
    for p in range(0,len(code)-3,4):
        pc=base+p
        target=decode_bl_target(u32(code,p),pc)
        if target is None or not(start<=target<end):continue
        counter[target]+=1
        if len(samples[target])<20:
            samples[target].append(pc)
    return counter,samples

def local_context(code,base,start,end):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    cs=Cs(CS_ARCH_ARM64,CS_MODE_ARM);cs.detail=True
    results=[]
    for i in cs.disasm(code[start-base:end-base],start):
        read,write=i.regs_access()
        results.append({"pc":i.address,"mnemonic":i.mnemonic,"operands":i.op_str,
                        "writes":[i.reg_name(x) for x in write],
                        "u32":f"{u32(code,i.address-base):08x}"})
    if len(results)!=(end-start)//4:
        raise ValueError("Original code region disassembly lost instructions")
    return results

def classify_local(instructions):
    x19=[]
    nearowner=[]
    prologues=[]
    returns=[]
    for n,i in enumerate(instructions):
        pc=i["pc"]
        if ("x19" in i["writes"] or "w19" in i["writes"]):
            x19.append(i)
        if i["mnemonic"] in ("ret","retab"):
            returns.append(pc)
        if i["mnemonic"]=="stp" and "x29, x30, [sp" in i["operands"]:
            # stp prologue heuristic; no claim of exact function boundary
            prologues.append(i)
        if i["mnemonic"]=="ldr":
            # Decode the actual instruction bytes, not string coincidences.
            l=ldrx(int(i["u32"],16))
            if l and l["offset"]==0x28:
                if abs(pc-OWNER_STORE)<=0x1300:
                    nearowner.append({"pc":pc,
                                      "base_register":f"x{l['base']}",
                                      "object_register":f"x{l['dst']}",
                                      "u32":i["u32"]})
    return {
        "x19_writes_in_region":x19,
        "x19_writes_nearest_prior_to_object_escape":[x for x in x19 if x["pc"]<OWNER_STORE][-30:],
        "stack_frame_prologue_candidates":prologues,
        "local_ret_sites":returns,
        "local_owner_field_0x28_loads":nearowner,
    }

def analyze(main,prev):
    sha=hashlib.sha256(main).hexdigest()
    if sha!=SHA or prev["report"]["source_exefs_sha256"]!=sha:
        raise ValueError("Native provenance mismatch")
    escape=prev["escape"]
    if (escape["verified_member_store_pc"]!=OWNER_STORE or
        escape["verified_vptr_write_pc"]!=VSTORE or
        escape["owner_member_offset"]!=0x28 or
        not escape["callee_saved_register_no_intervening_write"]):
        raise ValueError("Native x23 owner escape proof missing")
    kind,sections=get_sections(main)
    if kind!="NSO0":raise ValueError("NSO0 required")
    c=next(s for s in sections if s["name"]=="text")
    code,base=c["data"],c["mem_offset"]
    instructions=local_context(code,base,ROI_BEGIN,ROI_END)
    classified=classify_local(instructions)
    counts,sources=incoming_bl(code,base,ROI_BEGIN,ROI_END)
    calls=[
        {"callee_pc":pc,"native_direct_bl_call_count":n,
         "sample_bl_pcs":sources[pc],
         "is_nearby_prologue_candidate":any(x["pc"]==pc for x in classified["stack_frame_prologue_candidates"]),
         "proven_owner_this_type":False}
        for pc,n in counts.most_common(MAX_TARGETS)]
    # One queryable evidence region; don't commit full NSO or speculative callgraph.
    excerpt=[i for i in instructions if 0xD58E00<=i["pc"]<0xD59340]
    result={
        "report":{
            "status":"M9_LOCAL_OWNER_PROVENANCE_AND_INCOMING_CALL_XREF_CANDIDATES",
            "native_sha256":sha,"verified_member_store_pc":OWNER_STORE,
            "verified_owner_member_store":True,
            "region_start":ROI_BEGIN,"region_end":ROI_END,
            "raw_instructions_disassembled":len(instructions),
            "direct_bl_target_addresses_in_region":len(counts),
            "total_direct_bl_xrefs_into_region":sum(counts.values()),
            "verified_direct_owner_constructor_caller":0,
            "owner_x19_semantic_type_restored":False,
            "verified_specific_virtual_dispatch":0,
            "verified_kidsobjdb_getter":0,
            "verified_scene_quest_building_m7_text_fk":0,
            "limitations":[
                "Aarch64 BL targets in the region do not automatically target the object-construction entry.",
                "Frame prologue is a heuristic boundary; indirect control flow and jump tables may exist.",
                "x19 being callee-saved does not prove its original caller identity.",
                "Loads at owner+0x28 from unrelated objects are not semantic evidence."
            ]},
        "local_analysis":classified,
        "incoming_direct_bl_references":calls,
        "original_disassembly_context":excerpt,
    }
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main",type=Path,required=True)
    ap.add_argument("--owner-proof",type=Path,required=True)
    ap.add_argument("--dest",type=Path,required=True)
    a=ap.parse_args()
    out=analyze(a.main.read_bytes(),json.loads(a.owner_proof.read_text(encoding="utf-8")))
    a.dest.mkdir(parents=True,exist_ok=True)
    (a.dest/"exefs_owner_x19_local_callgraph.json").write_text(
        json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({**out["report"], "last_x19_defs":out["local_analysis"]["x19_writes_nearest_prior_to_object_escape"][-5:]},
                     ensure_ascii=False,indent=2))

if __name__=="__main__":main()
