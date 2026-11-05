#!/usr/bin/env python3
"""M28.1 original ARM64 local byte-hash recurrence verification.

For a 2-instruction chain:
  sub wTemp,wH,wH,lsl #5 = -31*wH (mod 2^32)
  sub wOut,wByte,wTemp  = wByte+31*wH (mod 2^32)

This is a *local arithmetic equality* only. Require a real preceding LDRB
for wByte and same temporary register. Decode from original source bytes,
not prior Capstone-rendered text. Search scope original complete NSO text.

If the native code uses a different pattern, the script returns zero and
does not claim the actual hash31 implementation has been located.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN,SHA_MAIN,arm64_window,branch_target,
)
from Scripts.resources.m28_original_nso_31_arithmetic_candidates import (
    shift_alu5,is_ldrb,is_ldrh,w32,OUT as OUTPUT,
)

OUT=OUTPUT

def sub_reg0(word):
    """Unshifted ARM64 SUB wD,wN,wM (no S and no extension)."""
    if (word&0xff200000)!=0x4b000000:return None
    if ((word>>22)&3)!=0 or ((word>>10)&0x3f)!=0:return None
    return {"dst":word&31,"lhs":(word>>5)&31,"rhs":(word>>16)&31}

def looks_branch_back(word,pc,origin):
    # Only direct B/BL in bounded range; conditional branches aren't decoded.
    t=branch_target(pc,word)
    return bool(t and origin-0x100<=t[0]<origin+0x80 and t[0]<pc)

def context(buf,base,first):
    start=max(0,first-base-16*4)
    end=min(len(buf),first-base+20*4)
    return [(base+k,w32(buf,k)) for k in range(start,end,4)]

def run():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:
        raise ValueError("Pinned original Pokopia 2.0.1 NSO source changed")
    kind,parts=get_sections(raw)
    if kind!="NSO0":raise ValueError("Original game NSO0 required")
    seg=next(p for p in parts if p["name"]=="text")
    buf,base=seg["data"],seg["mem_offset"]
    candidates=[]
    by_opcode=Counter()
    for off in range(0,len(buf)-4,4):
        w=w32(buf,off)
        shift=shift_alu5(w)
        if not shift or shift["width"]!=32:continue
        by_opcode[shift["op"]]+=1
        if not (shift["op"]=="SUB" and shift["same_source"] and
                not shift["sets_flags"]):
            continue
        pc=base+off
        dst=shift["dst"]
        hashreg=shift["lhs"]
        if dst==31 or hashreg==31:continue
        for step in range(1,7):
            next_off=off+4*step
            if next_off+4>len(buf):break
            sub=sub_reg0(w32(buf,next_off))
            if not sub or sub["rhs"]!=dst or sub["lhs"]==31:
                continue
            # Source chain can only be proven with no intervening write to
            # temp / hash / byte register. If nonadjacent, conservatively
            # mark register liveness UNPROVEN.
            byte_loads=[]
            for look in range(max(0,off-20*4),min(len(buf)-4,next_off+1),4):
                op=w32(buf,look)
                if is_ldrb(op) and (op&31)==sub["lhs"]:
                    byte_loads.append(base+look)
            if not byte_loads:continue
            lb=max(byte_loads)
            if lb>pc+step*4:continue
            near=context(buf,base,pc)
            backward=[{"pc":hex(p),"branch_target":hex(branch_target(p,v)[0])}
                      for p,v in near if looks_branch_back(v,p,pc)]
            grade=("EXACT_TWO_ADJACENT_SUB_ARITHMETIC_CHAIN_WITH_LDRB_CANDIDATE"
                   if step==1 and lb>=pc-12*4
                   else "NONADJACENT_REGISTER_LIVENESS_UNPROVEN")
            row={
                "negative_31_expression_pc":hex(pc),
                "negative_31_machine_word":f"{w:08x}",
                "final_byte_plus_31_hash_pc":hex(base+next_off),
                "final_machine_word":f"{w32(buf,next_off):08x}",
                "hash_input_register":f"w{hashreg}",
                "negative_temp_register":f"w{dst}",
                "byte_input_register":f"w{sub['lhs']}",
                "output_register":f"w{sub['dst']}",
                "candidate_ldrb_source_pc":hex(lb),
                "distance_in_instructions":step,
                "native_direct_backward_branch_sites":backward[:5],
                "source_byte_grade":grade,
                "arithmetic_hash31_identity_verified":step==1,
                "native_string_hash_function_verified":False,
                "native_KIDS_key_array_consumer_verified":False,
                "game_species_id_binding_verified":False,
            }
            candidates.append(row)
    # Distinct first+second opcode sites; a single hash loop may have one or
    # several byte-load sites, but only the latest source candidate is saved.
    unique={(x["negative_31_expression_pc"],x["final_byte_plus_31_hash_pc"]):x
            for x in candidates}
    entries=sorted(unique.values(),key=lambda x:(x["distance_in_instructions"],
                  int(x["negative_31_expression_pc"],16),
                  int(x["final_byte_plus_31_hash_pc"],16)))
    for r in entries[:30]:
        pc=int(r["negative_31_expression_pc"],16)
        r["original_assembly"]=arm64_window(buf,base,pc,0x34,0x50)
    summary={
        "game_version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "original_aligned_instruction_slots_scanned":len(buf)//4,
        "original_32bit_shift5_opcodes":dict(by_opcode),
        "local_two_sub_hash31_arithmetic_candidate_count":len(entries),
        "exact_adjacent_hash31_arithmetic_identities":sum(
            x["arithmetic_hash31_identity_verified"] for x in entries),
        "nonadjacent_requiring_register_liveness":sum(
            not x["arithmetic_hash31_identity_verified"] for x in entries),
        "shortlisted_assembly_windows":min(30,len(entries)),
        "native_hash31_function_and_input_proven":False,
        "native_kids_3543_key_lookup_consumer_proven":False,
        "native_pokemon_species_id_to_source_OID_proven":False,
        "warning":"Even an exact sub/byte/sub word chain is only original machine-code arithmetic, not proof of a KIDS icon hash or native species ID caller. LDRB byte-register liveness beyond adjacent instructions is not established.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m28_1_local_31_recurrence_candidates.json").write_text(
        json.dumps({"summary":summary,"candidates":entries[:100]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m28_1_local_31_recurrence_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    # SUB w8,w9,w9,LSL#5 -> -31*w9
    a=0x4B000000|(9<<16)|(5<<10)|(9<<5)|8
    got=shift_alu5(a)
    assert got and got["op"]=="SUB" and got["same_source"]
    # SUB w10,w11,w8 -> w11 - w8, with byte in w11.
    b=0x4B000000|(8<<16)|(11<<5)|10
    check=sub_reg0(b)
    assert check=={"dst":10,"lhs":11,"rhs":8}
    assert sub_reg0(a) is None
    print("PASS native 31-recurrence local two-sub ARM64 instruction decoder")
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest()
    else:run()
if __name__=="__main__":main()
