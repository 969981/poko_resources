#!/usr/bin/env python3
"""M9.15: trace one *specific* native object escape to owner+0x28.

Use byte-verified NSO 2.0.1, verify x0 -> x23 -> object vptr ->
[x19+0x28], then seek *owner member* load-site candidates. Unlike M9.14,
this does not scan arbitrary [vptr+0x38] dispatches alone. A matching
owner field offset is not proof of owner-class identity.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections

EXPECTED_SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ALLOC_RETURN_TO_PERSISTENT_REG=0xD591B0
VPTR_WRITE=0xD591C8
FINAL_OWNER_STORE=0xD59274
OWNER_MEMBER=0x28
VTABLE_CALLBACK_MEMBER=0x38
SAMPLE_LIMIT=200


def u32(buf,offset):
    return struct.unpack_from("<I",buf,offset)[0]


def ldrx(word):
    """ARM64 LDR Xt,[Xn,#uimm*8], no literal/sign-ext/pre-index."""
    if (word&0xffc00000)!=0xf9400000:
        return None
    return {"base":(word>>5)&31,"dst":word&31,"offset":((word>>10)&0xfff)*8}


def is_blr_reg(word,register):
    return (word&0xfffffc1f)==0xd63f0000 and ((word>>5)&31)==register


def disasm(code,base,start,end):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    if not(base<=start<=end<=base+len(code)) or ((start|end|base)&3):
        raise ValueError("Unmapped native text span")
    cs=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    cs.detail=True
    rows=[]
    for i in cs.disasm(code[start-base:end-base],start):
        read,write=i.regs_access()
        rows.append({"pc":i.address,"mnemonic":i.mnemonic,"operands":i.op_str,
                     "writes":[i.reg_name(x) for x in write],
                     "word":f"{u32(code,i.address-base):08x}"})
    if len(rows)!=(end-start)//4:
        raise ValueError("Native constructor text disassembly incomplete")
    return rows


def owner_escape(code,base,previous):
    if previous["report"]["original_exefs_sha256"]!=EXPECTED_SHA:
        raise ValueError("M9.12 proof baseline changed")
    stores=previous["verified_stores"]
    verified=[x for x in stores if x["site"]=="candidate_object_A"
              and x["verified_original_arm64_vptr_assignment"]
              and x["verified_callback_pointer_at_vptr_offset"]
              and x["written_pointer"]==0x32fdfa0
              and x["vtable_callback_offset"]==VTABLE_CALLBACK_MEMBER
              and x["table_callback_pc"]==0xd59420]
    if len(verified)!=1:
        raise ValueError("M9.12 object/vptr/callback identity missing")
    codeblock=disasm(code,base,ALLOC_RETURN_TO_PERSISTENT_REG,FINAL_OWNER_STORE+4)
    table={r["pc"]:r for r in codeblock}
    required={
        ALLOC_RETURN_TO_PERSISTENT_REG:("mov","x23, x0"),
        VPTR_WRITE:("stp","x8, xzr, [x23]"),
        FINAL_OWNER_STORE:("str","x23, [x19, #0x28]"),
    }
    for pc,(mnemonic,op) in required.items():
        r=table[pc]
        if r["mnemonic"]!=mnemonic or r["operands"]!=op:
            raise ValueError(f"Original ExeFS store dataflow mismatch: {pc:#x} {r}")
    clobbers=[
        r for r in codeblock if ALLOC_RETURN_TO_PERSISTENT_REG<r["pc"]<FINAL_OWNER_STORE
        and ({"x23","w23"}&set(r["writes"]))
    ]
    if clobbers:
        raise ValueError(f"x23 was overwritten before owner field write: {clobbers}")
    return {
        "status":"EXACT_NATIVE_OBJECT_ESCAPES_TO_OWNER_PLUS_0X28",
        "source_allocation_return_register":"x0",
        "saved_object_register":"x23",
        "save_object_pc":ALLOC_RETURN_TO_PERSISTENT_REG,
        "verified_vptr_write_pc":VPTR_WRITE,
        "vtable_address":0x32fdfa0,
        "vtable_callback_offset":VTABLE_CALLBACK_MEMBER,
        "callback_pc":0xd59420,
        "verified_member_store_pc":FINAL_OWNER_STORE,
        "owner_register":"x19",
        "owner_member_offset":OWNER_MEMBER,
        "owner_member_store_mnemonic":table[FINAL_OWNER_STORE]["mnemonic"]+" "+table[FINAL_OWNER_STORE]["operands"],
        "callee_saved_register_no_intervening_write":True,
        "instruction_window":codeblock,
        "owner_semantic_class_identity_verified":False,
        "specific_descriptor_dispatch_verified":False,
        "KIDSOBJDB_getter_verified":False,
        "M7_text_fk_verified":False,
    }


def find_owner_field_reads(code,base,limit=SAMPLE_LIMIT):
    """Only start from concrete [owner,#0x28] loads.

    Candidate chain: LDR object,[owner,+0x28] -> LDR vptr,[object]
    -> LDR callback,[vptr,+0x38] -> BLR callback.
    Each link must be within the following 12 instructions; the output
    is still untyped because x19's owner class is not established.
    """
    total=0
    results=[]
    matched=0
    contiguous=0
    exact_head=[]
    for pos in range(0,len(code)-4,4):
        raw=u32(code,pos)
        first=ldrx(raw)
        if first is None or first["offset"]!=OWNER_MEMBER:
            continue
        total+=1
        if len(exact_head)<50:
            exact_head.append({"pc":base+pos,"owner_register":f"x{first['base']}",
                               "loaded_object_register":f"x{first['dst']}",
                               "word":f"{raw:08x}"})
        # x31 is ZR or SP; not a safe object pointer in this strict load pattern.
        if first["dst"]==31:
            continue
        limitoff=min(len(code)-4,pos+4*13)
        chains=[]
        for s in range(pos+4,limitoff+1,4):
            second=ldrx(u32(code,s))
            if not second or second["base"]!=first["dst"] or second["offset"]!=0:
                continue
            if second["dst"]==31: continue
            for t in range(s+4,limitoff+1,4):
                third=ldrx(u32(code,t))
                if not third or third["base"]!=second["dst"] or third["offset"]!=VTABLE_CALLBACK_MEMBER:
                    continue
                if third["dst"]==31:continue
                for b in range(t+4,limitoff+1,4):
                    if is_blr_reg(u32(code,b),third["dst"]):
                        chains.append((s,t,b,second,third))
                        break
                if chains:break
            if chains:break
        if not chains:continue
        matched+=1
        s,t,b,second,third=chains[0]
        if (s,t,b)==(pos+4,pos+8,pos+12):
            contiguous+=1
        if len(results)<limit:
            results.append({
                "owner_member_load_pc":base+pos,
                "owner_member_offset":OWNER_MEMBER,
                "object_register":f"x{first['dst']}",
                "vptr_load_pc":base+s,
                "vptr_register":f"x{second['dst']}",
                "callback_slot_load_pc":base+t,
                "callback_register":f"x{third['dst']}",
                "blr_pc":base+b,
                "exact_four_instruction_chain":(s,t,b)==(pos+4,pos+8,pos+12),
                "words":[f"{u32(code,k):08x}" for k in (pos,s,t,b)],
                "intervening_register_clobber_proven_absent":False,
                "owner_class_identity_verified":False,
                "descriptor_callback_target_verified":False,
                "script_text_fk_verified":False,
                "grade":"OWNER_FIELD_OFFSET_AND_INDIRECT_SLOT_PATTERN_ONLY",
            })
    return {
        "all_native_ldr_from_owner_plus_0x28":total,
        "owner_member_plus_callback_pattern_candidates":matched,
        "four_instruction_exact_patterns":contiguous,
        "first_owner_member_load_sites":exact_head,
        "pattern_examples":results,
        "patterns_truncated":matched>limit,
    }


def analyze(main,previous):
    sha=hashlib.sha256(main).hexdigest()
    if sha!=EXPECTED_SHA:raise ValueError("Original NSO SHA-256 mismatch")
    fmt,sections=get_sections(main)
    if fmt!="NSO0":raise ValueError("NSO0 source required")
    code=next(x for x in sections if x["name"]=="text")
    owner=owner_escape(code["data"],code["mem_offset"],previous)
    readers=find_owner_field_reads(code["data"],code["mem_offset"])
    report={
        "status":"M9_PROVEN_OBJECT_ESCAPE_TO_OWNER_0X28_WITH_UNTYPED_READ_CANDIDATES",
        "source_exefs_sha256":sha,
        "verified_original_object_escape":True,
        "specific_vptr_and_callback_slot_bytes_verified":True,
        "owner_member_offset":OWNER_MEMBER,
        "verified_object_dispatch_to_specific_callback":0,
        "verified_owner_identity_or_registration":0,
        "verified_kidsobjdb_getters":0,
        "new_scene_quest_building_m7_text_foreign_keys":0,
        "limitations":[
            "Object pointer writes to x19+0x28; identity and lifetime of x19 are not yet known.",
            "Loads from unrelated classes at the same offset may produce false positive matches.",
            "Noncontiguous instruction patterns do not prove register identity across intervening code.",
            "Do not equate descriptor enumeration callback with a KIDSOBJDB text getter.",
        ],
    }
    return {"report":report,"escape":owner,"owner_field_consumers":readers}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main",type=Path,required=True)
    ap.add_argument("--m9-12",type=Path,required=True)
    ap.add_argument("--dest",type=Path,required=True)
    args=ap.parse_args()
    result=analyze(args.main.read_bytes(),json.loads(args.m9_12.read_text(encoding="utf-8")))
    args.dest.mkdir(parents=True,exist_ok=True)
    (args.dest/"exefs_owner_0x28_escape_trace.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({**result["report"],
        **{k:v for k,v in result["owner_field_consumers"].items() if k not in ("first_owner_member_load_sites","pattern_examples")}},
        ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
