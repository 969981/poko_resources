#!/usr/bin/env python3
"""M28: original NSO0 AArch64 candidate implementation scan for x31 string hashing.

Fail-closed evidence levels:
* native instruction exact -> recognized 32-bit ADD/SUB (register shifted by 5)
  or MADD/MUL supplied by a 31 MOVZ in 14 instructions;
* static lexical proximity to byte loads and a backward branch can prioritize;
* a hash recurrence, its user, KIDS class, and gameplay species ID are NOT
  proven merely by one or more of these opcodes.

No runtime memory writes, no game-ID or portrait mapping.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN, SHA_MAIN, arm64_window, branch_target
)

OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M28")
LIMIT=250
# A handful of absolute original NSO research anchors. Merely observing a
# native branch among the candidates does not infer a shared program path.
ANCHORS={
    "native_property_descriptor_method":0xDD1B48,
    "native_type_getter":0xDD1C30,
    "pokemon_dex_id_string_reference":0x1136AA4,
    "main_pokemon_list_string_reference":0x5FD168,
    "generic_type_register":0x1FDC1E0,
}

def w32(b,p):return struct.unpack_from("<I",b,p)[0]

def shift_alu5(word):
    # ARM64 add/sub shifted register 32-bit, allow 64-bit for context.
    # [31] sf [30] op [29] S [28:24]=01011 [23:22] shift.
    if word&0x1F200000!=0x0B000000:return None
    if (word>>22)&3:return None
    shift=(word>>10)&0x3f
    if shift!=5:return None
    src=(word>>5)&31;other=(word>>16)&31
    return {
        "width":64 if word>>31 else 32,
        "op":"SUB" if (word>>30)&1 else "ADD",
        "sets_flags":bool((word>>29)&1),
        "dst":word&31,"lhs":src,"shift_src":other,
        "same_source":src==other,
        "shift":shift,
    }

def is_movz31(word):
    # 32- and 64-bit MOVZ value 0x001F, low 16 bits, shift=0.
    return (word&0x7F800000)==0x52800000 and (
        ((word>>5)&0xffff)==31 and ((word>>21)&3)==0
    )

def madd_src(word):
    # Add/subtract product instructions (32/64-bit), MADD=0x1B000000.
    # The 0x1FE08000 mask includes bit15 for MSUB.
    if (word&0x1FE08000)!=0x1B000000:return None
    return {
        "width":64 if word>>31 else 32,
        "dst":word&31,
        "rn":(word>>5)&31,
        "rm":(word>>16)&31,
        "ra":(word>>10)&31,
        "is_mul_alias":((word>>10)&31)==31,
    }

def is_ldrb(word):
    return (word&0xFFC00000)==0x39400000 or (word&0xFFE00C00)==0x38400000

def is_ldrh(word):
    return (word&0xFFC00000)==0x79400000

def code_context(buf,base,pc,lookback=20,lookforward=24):
    off=pc-base
    start=max(0,off-lookback*4)
    end=min(len(buf)&~3,off+(lookforward+1)*4)
    return [(base+p,w32(buf,p)) for p in range(start,end,4)]

def evidence(pc,buf,base,form,details,near,near31=None):
    byte_loads=[hex(p) for p,w in near if is_ldrb(w)]
    half_loads=[hex(p) for p,w in near if is_ldrh(w)]
    back=[]
    for p,w in near:
        b=branch_target(p,w)
        if b and b[0]<p and p-pc<=0x90 and p-pc>=-0x30:
            back.append({"pc":hex(p),"target":hex(b[0]),"kind":b[1]})
    score=(5 if byte_loads else 0)+(1 if half_loads else 0)+(
        2 if back else 0)+(3 if form=="MADD_WITH_LOCAL_MOVZ31" else 0)+(
        2 if details.get("same_source") else 0)
    return {
        "original_pc":hex(pc),
        "original_word":f"{w32(buf,pc-base):08x}",
        "instruction_family":form,
        "opcode_fields":details,
        "native_31_movz_local":hex(near31) if near31 is not None else "",
        "nearby_ldrb_sites":byte_loads,
        "nearby_ldrh_sites":half_loads,
        "nearby_direct_backward_branches":back[:8],
        "ranking_score":score,
        "original_31_recurrence_proven":False,
        "KIDS_icon_registry_consumer_proven":False,
        "native_game_species_id_binding_proven":False,
    }

def detect():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:raise ValueError("Pinned original NSO SHA mismatch")
    kind,parts=get_sections(raw)
    if kind!="NSO0":raise ValueError("Original main NSO0 required")
    sec=next(x for x in parts if x["name"]=="text")
    buf,base=sec["data"],sec["mem_offset"]
    if len(buf)%4:raise ValueError("Unexpected unaligned original NSO text")
    movz_map={}
    instructions=[]
    shift_candidates=[]
    madd_candidates=[]
    byte_load_count=0
    direct_bl_targets=Counter()
    direct_b_targets=Counter()
    count=0
    for off in range(0,len(buf),4):
        count+=1
        word=w32(buf,off)
        pc=base+off
        if is_ldrb(word):byte_load_count+=1
        if (word&0xfc000000)==0x94000000 or (word&0xfc000000)==0x14000000:
            item=branch_target(pc,word)
            if item:
                (direct_bl_targets if item[1]=="BL" else direct_b_targets)[item[0]]+=1
        if is_movz31(word):
            reg=word&31
            movz_map.setdefault(reg,[]).append(pc)
        alu=shift_alu5(word)
        if alu and alu["width"]==32:
            shift_candidates.append((pc,alu))
        mad=madd_src(word)
        if mad and mad["width"]==32:
            madd_candidates.append((pc,mad))
    # Avoid confounding a constant installed earlier in another function.
    # A constant MOVZ must be in preceding <=14 *instructions*, and same
    # physical register as one of the multiplication operands.
    candidates=[]
    for pc,alu in shift_candidates:
        near=code_context(buf,base,pc)
        candidates.append(evidence(pc,buf,base,"ADD_SUB_LSL5",alu,near))
    madd_checked=0
    for pc,mad in madd_candidates:
        near31=[]
        for reg in (mad["rn"],mad["rm"]):
            if reg not in movz_map:continue
            # binary-search for predecessor
            from bisect import bisect_left
            sites=movz_map[reg]
            idx=bisect_left(sites,pc)-1
            if idx>=0 and 0<pc-sites[idx]<=14*4:
                # This doesn't prove register liveness; a later write may
                # overwrite the 31 constant. Mark as candidate only.
                near31.append(sites[idx])
        if not near31:continue
        madd_checked+=1
        near=code_context(buf,base,pc)
        candidates.append(evidence(pc,buf,base,"MADD_WITH_LOCAL_MOVZ31",mad,near,min(near31)))
    ranked=sorted(candidates,key=lambda r:(-r["ranking_score"],int(r["original_pc"],16)))
    for c in ranked[:LIMIT]:
        pc=int(c["original_pc"],16)
        c["native_asm_window"]=arm64_window(buf,base,pc,0x28,0x48)
        # Precomputed across text exactly once: avoid 250 full NSO scans.
        # A direct branch to an interior instruction is rarely a function
        # entry, so these counts are context only.
        c["direct_BL_branch_to_instruction_count"]=direct_bl_targets[pc]
        c["direct_B_branch_to_instruction_count"]=direct_b_targets[pc]
    anchors={}
    for label,pc in ANCHORS.items():
        if not base<=pc<base+len(buf):raise ValueError(f"Original NSO anchor missing {label}")
        anchors[label]=arm64_window(buf,base,pc,0x28,0x48)
    summary={
        "version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "original_code_segment_length":len(buf),
        "original_aligned_instruction_slots_scanned":count,
        "original_native_ldrb_instruction_count":byte_load_count,
        "add_sub_shift5_word_candidates":len(shift_candidates),
        "madd_mul_instruction_count":len(madd_candidates),
        "madd_mul_near_movable_31_constant_candidate_count":madd_checked,
        "combined_candidate_count":len(candidates),
        "candidate_count_with_nearby_byte_load":sum(bool(c["nearby_ldrb_sites"]) for c in candidates),
        "candidate_count_with_nearby_backward_direct_branch":sum(bool(c["nearby_direct_backward_branches"]) for c in candidates),
        "ranked_candidate_windows_saved":min(LIMIT,len(ranked)),
        "native_hash31_function_verified":False,
        "native_kids_twin_array_consumer_verified":False,
        "game_species_id_to_array_key_verified":False,
        "caveat":"32-bit LSL5 ADD/SUB and nearby MADD with MOVZ #31 are instruction-pattern leads, not verified hash function implementations. Candidate code may include unrelated arithmetic.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m28_31_arithmetic_candidates.json").write_text(
        json.dumps({"summary":summary,"ranked_candidates":ranked[:LIMIT],
                    "anchor_disassembly":anchors},ensure_ascii=False,indent=2)+"\n",
        encoding="utf-8")
    (OUT/"m28_31_instruction_search_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    # add w1,w2,w3,lsl #5
    add=0x0B000000|(3<<16)|(5<<10)|(2<<5)|1
    decoded=shift_alu5(add)
    assert decoded and decoded["dst"]==1 and decoded["lhs"]==2
    assert decoded["shift_src"]==3 and decoded["shift"]==5
    assert shift_alu5(add|(1<<10)) is None
    assert is_movz31(0x528003E4) and not is_movz31(0x528003C4)
    # madd w1,w2,w3,w4
    mad=0x1B000000|(3<<16)|(4<<10)|(2<<5)|1
    assert madd_src(mad) and madd_src(mad)["rn"]==2
    assert is_ldrb(0x39400020)
    print("PASS AArch64 x31 arithmetic detection word masks and fail-closed test")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest()
    else:detect()

if __name__=="__main__":main()
