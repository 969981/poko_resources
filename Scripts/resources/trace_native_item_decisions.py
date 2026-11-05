#!/usr/bin/env python3
"""M11.2: source-register-aware ARM64 conditional users of raw +0x26/+0x3a.

A direct CMP/TST/CBZ/TBZ of a field-loaded register proves that the *raw
byte* participates in a branch/condition in this code fragment. It does NOT
prove the structure's identity, name or gameplay enum.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

try:
    from .trace_native_item_provenance import (
        scan, get_sections, MAIN_SHA, ITEM_SHA, canonical,
        write_names, is_barrier, producer_chain, windows,
    )
except ImportError:
    from trace_native_item_provenance import (
        scan, get_sections, MAIN_SHA, ITEM_SHA, canonical,
        write_names, is_barrier, producer_chain, windows,
    )

OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M11")
HIGH_VALUE_IMMEDIATES={4,6,8,10,15,16,18,19,99,100,255}
CONDITIONS={"cmp","cmn","tst","cbz","cbnz","tbz","tbnz"}


def scan_user(md, code, base, site, lookahead=24):
    from capstone.arm64 import ARM64_OP_REG, ARM64_OP_IMM
    pc=site["pc"]
    target="x"+str(site["target_register"])
    offset=pc-base
    seq=list(md.disasm(code[offset+4:offset+4+4*lookahead],pc+4))
    events=[]
    last=pc
    for idx,insn in enumerate(seq):
        if insn.address != last+4:
            break
        last=insn.address
        ops=insn.operands
        source_reg=bool(ops and ops[0].type==ARM64_OP_REG and
                        canonical(insn.reg_name(ops[0].reg))==target)
        if source_reg and insn.mnemonic in CONDITIONS:
            immediate=(int(ops[1].imm) if len(ops)>1 and ops[1].type==ARM64_OP_IMM
                       else None)
            events.append({
                "kind":"RAW_FIELD_REGISTER_USED_IN_CONDITION",
                "pc":hex(insn.address),
                "assembly":insn.mnemonic+" "+insn.op_str,
                "immediate":immediate,
                "byte_distance":insn.address-pc,
                "field_value_register":target
            })
        elif idx<=1 and source_reg and insn.mnemonic in ("strb","strh","str","stur"):
            events.append({
                "kind":"IMMEDIATE_RAW_FIELD_STORE",
                "pc":hex(insn.address),
                "assembly":insn.mnemonic+" "+insn.op_str,
                "byte_distance":insn.address-pc
            })
        if is_barrier(insn) or target in write_names(insn):
            break
    return events


def analyze(main: bytes, item_table: bytes, max_output=80):
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
    main_sha=hashlib.sha256(main).hexdigest()
    item_sha=hashlib.sha256(item_table).hexdigest()
    if main_sha != MAIN_SHA or item_sha != ITEM_SHA:
        raise ValueError("ORIGINAL_SOURCE_SHA_MISMATCH")
    kind,parts=get_sections(main)
    if kind!="NSO0":
        raise ValueError("UNKNOWN_NSO_FORMAT")
    seg=next(p for p in parts if p["name"]=="text")
    code,base=seg["data"],seg["mem_offset"]
    fields,_,_=scan(code,base)
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    md.detail=True
    counters=Counter()
    results=[]
    for off in (0x26,0x3a):
        for site in fields[off]:
            events=scan_user(md,code,base,site)
            counters["raw_loads_"+hex(off)]+=1
            matches=[e for e in events if e["kind"]=="RAW_FIELD_REGISTER_USED_IN_CONDITION"]
            stores=[e for e in events if e["kind"]=="IMMEDIATE_RAW_FIELD_STORE"]
            if stores:
                counters["immediate_stores_"+hex(off)]+=1
            if not matches:
                continue
            counters["condition_sites_"+hex(off)]+=1
            immediate_hits=[x["immediate"] for x in matches
                            if x["immediate"] is not None and x["immediate"] in HIGH_VALUE_IMMEDIATES]
            score=20 if off==0x26 else 15
            score+=4*len(immediate_hits)
            score+=max(0,8-min(x["byte_distance"] for x in matches)//4)
            score-=2*len(stores)
            results.append({
                "pc":hex(site["pc"]), "raw_ldr_word":site["word"],
                "struct_offset":hex(off),
                "base_register":"x"+str(site["base_register"]),
                "raw_value_register":"x"+str(site["target_register"]),
                "immediate_store_before_branch":bool(stores),
                "conditions":matches,
                "priority_constants_in_conditions":immediate_hits,
                "base_register_local_producer":producer_chain(
                    md,code,base,site["pc"],"x"+str(site["base_register"])),
                "review_priority_score":score,
                "confidence":"ORIGINAL_RAW_FIELD_CONDITIONAL_CONSUMER_STRUCT_ID_UNVERIFIED"
            })
    results.sort(key=lambda r:(-r["review_priority_score"],int(r["pc"],16)))
    for r in results[:max_output]:
        r["disassembly_window"]=windows(md,code,base,int(r["pc"],16),before=56,after=96)
    return {
        "status":"NATIVE_RAW_FIELD_CONDITIONS_FOUND__ITEM_BASE_UNVERIFIED",
        "main_sha256":main_sha,"item_table_sha256":item_sha,
        "text_bytes":len(code),"text_rva":hex(base),
        "counters":dict(sorted(counters.items())),
        "conditional_candidate_total":len(results),
        "top_candidates":results[:max_output],
        "confirmed_item_record_base":False,
        "confirmed_material_type_enum":False,
        "confirmed_inventory_quantity_limit":False,
        "limitations":[
            "Register-use confirmation does not establish that the base points at a 00983.bin 68-byte item record.",
            "Immediate comparisons may belong to arbitrary record types or values; do not name categories without a parser/caller or game behavior.",
            "The scan examines only linear post-load windows up to 24 ARM64 instructions, not full CFG or all aliases."
        ]
    }


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,default=Path("2.0.1/exefs/main"))
    p.add_argument("--table",type=Path,default=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin"))
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    report=analyze(a.main.read_bytes(),a.table.read_bytes())
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"field_condition_dataflow.json").write_text(json.dumps(
        report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    small={k:v for k,v in report.items() if k!="top_candidates"}
    small["shortlist"]=[{k:r[k] for k in (
        "pc","struct_offset","base_register","raw_value_register","conditions",
        "priority_constants_in_conditions","base_register_local_producer","confidence")}
        for r in report["top_candidates"][:24]]
    (a.out/"field_condition_shortlist.json").write_text(json.dumps(
        small,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("M11_2_RESULT",json.dumps({k:report[k] for k in (
        "status","counters","conditional_candidate_total",
        "confirmed_item_record_base","confirmed_material_type_enum")},separators=(",",":")))
    print("M11_2_TOP",json.dumps(small["shortlist"][:12],separators=(",",":")))


if __name__=="__main__":
    main()
