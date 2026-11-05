#!/usr/bin/env python3
"""M9.21: complete bounded instruction bodies for four *exact* owner callbacks.

Correct M9.20's early stop at computed jump-table BR. Decode each native
method to the next validated sibling entry: cleanup, cleanup sibling,
constructor, constructor sibling. Recover x3->x19 and owner+0x28 reads,
show complete native instructions and explicit direct branches. Any
indirect dispatch is an unverified potential target until exact vptr
instance and control flow are demonstrated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_owner_object_escape import ldrx, is_blr_reg

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
METHODS={
    "cleanup":(0xd58e34,0xd58f50),
    "cleanup_sibling":(0xd58f60,0xd58ff4),
    "constructor":(0xd590e0,0xd592b4),
    "constructor_sibling":(0xd592b4,0xd593ac),
}
TARGET_RE=re.compile(r"#(0x[0-9a-f]+|[0-9]+)$",re.I)


def u32(b,o):return struct.unpack_from("<I",b,o)[0]


def disassemble(code,base,first,last):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    if first%4 or last%4 or not base<=first<last<=base+len(code):
        raise ValueError("Unmapped callback function range")
    cs=Cs(CS_ARCH_ARM64,CS_MODE_ARM);cs.detail=True
    ins=[]
    for i in cs.disasm(code[first-base:last-base],first):
        read,write=i.regs_access()
        ins.append({
            "pc":i.address,"mnemonic":i.mnemonic,"operands":i.op_str,
            "writes":[i.reg_name(x) for x in write],
            "word":f"{u32(code,i.address-base):08x}",
        })
    if len(ins)!=(last-first)//4:
        raise ValueError("Unexpected non-disassemblable instruction in exact source range")
    return ins


def code_edges(ins,entry,end):
    edges=[]
    for x in ins:
        mn=x["mnemonic"];pc=x["pc"]
        kind=None
        if mn=="b" or mn.startswith(("b.","cbz","cbnz","tbz","tbnz")):
            kind="branch"
        elif mn=="br":
            kind="indirect_jump"
        if kind is None:continue
        target=None
        m=TARGET_RE.search(x["operands"])
        if m:
            target=int(m.group(1),0)
        edges.append({"source_pc":pc,"kind":kind,"target_pc":target,
                      "target_in_current_method":target is not None and entry<=target<end,
                      "resolved":target is not None})
    return edges


def inspect_function(name,code,base,entry,end):
    ins=disassemble(code,base,entry,end)
    table={x["pc"]:x for x in ins}
    alias=[x for x in ins if x["mnemonic"]=="mov" and x["operands"]=="x19, x3"]
    owner_reads=[]
    direct_slot38=[]
    for pos,x in enumerate(ins):
        if x["mnemonic"]!="ldr":continue
        l=ldrx(int(x["word"],16))
        if not l:continue
        if l["offset"]==0x28 and l["base"] in (3,19):
            owner_reads.append({"pc":x["pc"],"base_register":f"x{l['base']}",
                                "loaded_register":f"x{l['dst']}",
                                "preceding_x3_to_x19_alias":any(y["pc"]<x["pc"] for y in alias),
                                "verified_original_instruction_bytes":True,
                                "owner_type_verified":False})
        if l["offset"]==0x38:
            calls=[]
            for j in ins[pos+1:pos+9]:
                if is_blr_reg(int(j["word"],16),l["dst"]):
                    calls.append(j["pc"])
            direct_slot38.append({
                "load_pc":x["pc"],"base_register":f"x{l['base']}",
                "callback_register":f"x{l['dst']}",
                "blr_same_reg_within_next8_instructions":calls,
                "target_callback_proven":False,
            })
    return {
        "name":name,"entry_pc":entry,"end_exclusive_pc":end,
        "complete_original_linear_instructions_verified":True,
        "instruction_count":len(ins),
        "x3_to_x19_exact_sites":[x["pc"] for x in alias],
        "owner_plus_0x28_reads":owner_reads,
        "slot0x38_callback_load_shapes":direct_slot38,
        "direct_branch_and_jump_edges":code_edges(ins,entry,end),
        "computed_jump_table_br_count":sum(x["mnemonic"]=="br" for x in ins),
        "actual_vptr0x32fdfa0_caller_proven":False,
        "runtime_object_identity_proven":False,
        "M7_text_fk_proven":False,
        "native_instructions":ins,
    }


def analyze(main,prior):
    sha=hashlib.sha256(main).hexdigest()
    if sha!=SHA or prior["report"]["original_exefs_sha256"]!=sha:
        raise ValueError("Wrong source NSO or M9.20 evidence")
    siblings={(r["table"],r["relative_to_root_entry"]):r["native_function_pc"]
              for r in prior["callbacks"]}
    assert_map={
        ("cleanup_table",0):METHODS["cleanup"][0],
        ("cleanup_table",24):METHODS["cleanup_sibling"][0],
        ("constructor_table",0):METHODS["constructor"][0],
        ("constructor_table",8):METHODS["constructor_sibling"][0],
        ("constructor_table",16):METHODS["constructor_sibling"][1],
    }
    if any(siblings.get(k)!=v for k,v in assert_map.items()):
        raise ValueError("M9.20 source function boundary changed")
    fmt,parts=get_sections(main)
    if fmt!="NSO0":raise ValueError("Expected NSO0")
    text=next(x for x in parts if x["name"]=="text")
    data=[inspect_function(n,text["data"],text["mem_offset"],start,end)
          for n,(start,end) in METHODS.items()]
    report={
        "status":"M9_COMPLETE_BOUNDED_OWNER_CALLBACK_BODIES",
        "source_exefs_sha256":sha,
        "exact_callback_functions_fully_decoded":len(data),
        "native_instructions_decoded":sum(x["instruction_count"] for x in data),
        "original_x3_to_x19_aliases":sum(len(x["x3_to_x19_exact_sites"]) for x in data),
        "original_owner_plus_0x28_ldr_reads":sum(len(x["owner_plus_0x28_reads"]) for x in data),
        "original_vptr_plus_0x38_ldr_shapes":sum(len(x["slot0x38_callback_load_shapes"]) for x in data),
        "computed_jump_table_indirect_branches":sum(x["computed_jump_table_br_count"] for x in data),
        "exact_inner_object_vptr_callback_runtime_dispatch_proven":0,
        "verified_script_to_M7_foreign_keys":0,
        "missing_source_fdata_hashes":["ea42a223","5c83387f","898afd6d"],
        "limitations":[
            "Method boundaries are based on M9.18 adjacent native static function pointers; computed jump tables may target code not visited in simple linear order.",
            "Exact instruction body coverage does not itself establish CFG feasibility, x3 owner instance identity or runtime BLR dispatch.",
            "A vptr+0x38 LDR in this class is not necessarily the inner object vptr at 0x32fdfa0.",
            "The RDB-backed original RNK files remain missing; no native IRNK names are fabricated.",
        ],
    }
    return {"report":report,"methods":data}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--m9-20",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    a=p.parse_args()
    report=analyze(a.main.read_bytes(),json.loads(a.m9_20.read_text(encoding="utf-8")))
    a.dest.mkdir(parents=True,exist_ok=True)
    (a.dest/"exefs_owner_complete_callback_control_flow.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["report"],ensure_ascii=False,indent=2))


if __name__=="__main__":main()
