#!/usr/bin/env python3
"""M28.2: verify original ARM64 33*h - 2*h (=31*h) instruction paths.

AArch64 optimizer may encode a 31 multiplier using:
  add wT,wH,wH,lsl#5   ; wT=33*h
  sub wP,wT,wH,lsl#1   ; wP=31*h
  add wOut,wP,wChar    ; optional char from native LDRB

The first 2 instructions are provably 31*h only if adjacent and registers
are exact. Nonadjacent results are candidates, not proven live values.
A nearby LDRB is not a proven string byte or link to KIDS hash fields.

Also exports EVERY same-source LSL#5 instruction with bounded context
for inspecting alternate optimizer idioms. No arbitrary gameplay ID mapping.
"""
from __future__ import annotations
import argparse
import csv
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
    shift_alu5,is_ldrb,w32,OUT,
)

def shifted_reg(word,expected_op=None):
    # 32-bit ADD/SUB (shifted-register).
    if (word&0x1F200000)!=0x0B000000 or word>>31:return None
    if (word>>29)&1:return None # flags-changing variants excluded
    shift_type=(word>>22)&3
    if shift_type!=0:return None
    op="SUB" if (word>>30)&1 else "ADD"
    if expected_op is not None and op!=expected_op:return None
    return {"dst":word&31,"lhs":(word>>5)&31,
            "rhs":(word>>16)&31,"shift":(word>>10)&0x3f,"op":op}

def recent_byte(buf,off,reg):
    # Scan 20 prior instructions for a real LDRB immediate/LDURB;
    # intervening register writes are not proven safe.
    for prev in range(off-4,max(-1,off-21*4),-4):
        if prev<0:break
        word=w32(buf,prev)
        if is_ldrb(word) and (word&31)==reg:return prev
    return None

def summarize():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:
        raise ValueError("Original NSO source changed")
    kind,parts=get_sections(raw)
    if kind!="NSO0":raise ValueError("Not a pinned NSO0")
    sec=next(v for v in parts if v["name"]=="text")
    buf,base=sec["data"],sec["mem_offset"]
    rows=[]
    hits=[]
    for off in range(0,len(buf)-3,4):
        word=w32(buf,off)
        d=shifted_reg(word,"ADD")
        if not d or d["shift"]!=5:continue
        if d["lhs"]!=d["rhs"]:
            continue
        pc=base+off
        row={
            "original_pc":hex(pc),
            "original_word":f"{word:08x}",
            "hash_source_register":f"w{d['lhs']}",
            "33_times_temp_register":f"w{d['dst']}",
            "exact_33h_original_opcode":True,
            "nearest_ldrb_pc":"",
            "nearby_ldrb_status":"NOT_CHECKED_AS_FULL_LIVENESS",
            "two_opcode_31h_identity_found":False,
            "two_opcode_31h_identity_adjacent":False,
            "adjacent_character_add_verified":False,
            "native_hash_function_verified":False,
            "native_kids_query_consumer_verified":False,
            "native_species_ID_verified":False,
        }
        # Detect 33h-2h by exact original register relationships.
        for steps in range(1,9):
            next_at=off+4*steps
            if next_at+4>len(buf):break
            sub=shifted_reg(w32(buf,next_at),"SUB")
            if not sub or sub["shift"]!=1:continue
            if sub["lhs"]!=d["dst"] or sub["rhs"]!=d["lhs"]:
                continue
            # wT = wH+(wH<<5), sub(wT,wH<<1)=31h
            row["two_opcode_31h_identity_found"]=True
            row["two_opcode_31h_identity_adjacent"]=steps==1
            hit={
                "first_33h_pc":hex(pc),
                "second_minus_2h_pc":hex(base+next_at),
                "first_33h_word":f"{word:08x}",
                "second_minus_2h_word":f"{w32(buf,next_at):08x}",
                "steps":steps,
                "source_hash_register":f"w{d['lhs']}",
                "first_temp_register":f"w{d['dst']}",
                "second_31h_register":f"w{sub['dst']}",
                "arithmetic_31h_adjacent_proven":steps==1,
                "source_register_liveness_if_nonadjacent":"UNVERIFIED",
                "character_add_afterward_source_verified":False,
                "native_game_id_consumer_verified":False,
            }
            # Look for immediate next ADD operation consuming 31h temp and
            # a byte-loaded register; grade full chain syntax conservatively.
            for j in range(1,5):
                next2=next_at+4*j
                if next2+4>len(buf):break
                add=shifted_reg(w32(buf,next2),"ADD")
                if not add or add["shift"]!=0:continue
                if add["lhs"]==sub["dst"]:
                    bytereg=add["rhs"]
                elif add["rhs"]==sub["dst"]:
                    bytereg=add["lhs"]
                else:continue
                prev=recent_byte(buf,off,bytereg)
                if prev is None:continue
                row["nearest_ldrb_pc"]=hex(base+prev)
                row["adjacent_character_add_verified"]=(steps==1 and j==1)
                hit["final_character_add_pc"]=hex(base+next2)
                hit["loaded_byte_register"]=f"w{bytereg}"
                hit["preceding_ldrb_pc"]=hex(base+prev)
                hit["contiguous_33minus2_plus_char_arithmetic"]=steps==1 and j==1
                # Even consecutive arithmetic does NOT prove that a
                # prior LDRB source remained live.
                hit["ldrb_byte_register_liveness"]="UNVERIFIED" if prev<off-4 else "ADJACENT_BEFORE_CHAIN"
                break
            hits.append(hit)
            break
        rows.append(row)
    rows.sort(key=lambda x:int(x["original_pc"],16))
    hits.sort(key=lambda x:(x["steps"],int(x["first_33h_pc"],16)))
    shortlist=[]
    for x in hits[:24]:
        pc=int(x["first_33h_pc"],16)
        shortlist.append({**x,"original_asm":arm64_window(buf,base,pc,0x28,0x50)})
    for x in rows:
        if x["nearest_ldrb_pc"]:continue
        off=int(x["original_pc"],16)-base
        for pre in range(max(0,off-15*4),min(len(buf),off+15*4),4):
            if is_ldrb(w32(buf,pre)):
                x["nearest_ldrb_pc"]=hex(base+pre)
                break
    summary={
        "game_version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "native_32_bit_same_source_ADD_LSL5_count":len(rows),
        "native_33h_minus_2h_local_pattern_count":len(hits),
        "exact_adjacent_33h_minus_2h_31h_expression_count":sum(
            x["arithmetic_31h_adjacent_proven"] for x in hits),
        "complete_adjacent_33h_minus_2h_plus_character_syntactic_count":sum(
            x.get("contiguous_33minus2_plus_char_arithmetic",False) for x in hits),
        "same_source_ADD_LSL5_with_nearby_LDRB_count":sum(
            bool(x["nearest_ldrb_pc"]) for x in rows),
        "saved_original_asm_windows":len(shortlist),
        "native_string_hash31_implementation_proven":False,
        "native_kids_registry_key_lookup_proven":False,
        "native_species_ID_to_original_array_slot_proven":False,
        "warning":"This is a narrowly specified optimizer idiom, not an exhaustive hash31 implementation search. Even exact native 31*h arithmetic does not establish a string hash or which KIDS icon array is used.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/"m28_2_native_shift5_same_source_survey.csv").open("w",newline="",encoding="utf-8") as f:
        if rows:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]))
            writer.writeheader();writer.writerows(rows)
        else:f.write("original_pc\n")
    (OUT/"m28_2_33minus2_byte_chain_dossier.json").write_text(
        json.dumps({"summary":summary,"candidate_chains":shortlist},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m28_2_33minus2_source_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    # ADD w8,w9,w9, LSL #5 -> w8=33*w9.
    a=0x0B000000|(9<<16)|(5<<10)|(9<<5)|8
    # SUB w10,w8,w9, LSL #1 -> w10=31*w9.
    b=0x4B000000|(9<<16)|(1<<10)|(8<<5)|10
    x=shifted_reg(a,"ADD");y=shifted_reg(b,"SUB")
    assert x and y and x["lhs"]==x["rhs"]
    assert y["lhs"]==x["dst"] and y["rhs"]==x["lhs"]
    assert x["shift"]==5 and y["shift"]==1
    assert shifted_reg(b,"ADD") is None
    assert ((33-2)*0x12345678)&0xffffffff == (31*0x12345678)&0xffffffff
    print("PASS native 33h-minus-2h arithmetic bitmask and algebra")
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:summarize()
if __name__=="__main__":main()
