#!/usr/bin/env python3
"""M9.5: prove AArch64 descriptor-writer use of some KIDSOBJDB hash constants.

This is code-level consumption of a *constant*, NOT proof of a runtime
KIDSOBJDB property lookup, scene/quest reference or matching property label.
Resolve ADRP+ADD rodata pointers around MOVZ/MOVK hash stores and preserve
their exact instruction addresses for follow-up basic-block call-chain work.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import struct
from pathlib import Path
try:
    from .trace_native_species_item_callers import get_sections
    from .m9_rnk_exefs_xrefs import decode_adrp,decode_add
except ImportError:
    from trace_native_species_item_callers import get_sections
    from m9_rnk_exefs_xrefs import decode_adrp,decode_add

REGS=re.compile(r"^([wx]\d+),\s*([wx]\d+),\s*\[x(\d+)")
MAX_WINDOW=1600

def u32(data,p):return struct.unpack_from("<I",data,p)[0]

def referenced_data(sections,address):
    for part in sections:
        if part["name"] not in ("rodata","data"):continue
        off=address-part["mem_offset"]
        data=part["data"]
        if off<0 or off>=len(data):continue
        preview=data[off:min(len(data),off+160)]
        nul=preview.find(b"\0")
        raw=preview[:nul] if nul>=0 else preview
        try:
            text=raw.decode("utf-8","strict")
            printable=bool(text) and len(text)<128 and (
                sum(c.isprintable() or c.isspace() for c in text)/len(text)>=.95)
        except UnicodeDecodeError:
            text=""
            printable=False
        return {"section":part["name"],"target_va":address,
                "raw_prefix_hex":preview[:36].hex(),
                "candidate_string":text if printable else "",
                "interpretation":"C_STRING_CANDIDATE_NOT_FIELD_NAME" if printable
                    else "BINARY_OR_UNDECODED"}
    return {"section":"UNMAPPED","target_va":address,
            "raw_prefix_hex":"","candidate_string":"",
            "interpretation":"UNRESOLVED_ADDRESS"}

def parse_stp_registers(insn):
    if insn.mnemonic!="stp":return None
    m=REGS.match(insn.op_str)
    if not m:return None
    return m.group(1),m.group(2),int(m.group(3))

def trace_descriptor_site(code,base,sections,candidate):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    first=int(candidate["text_va_movz"])
    second=int(candidate["text_va_movk"])
    p=first-base
    if p<0 or p>=len(code):raise ValueError(f"MOVZ outside NSO text: {first:#x}")
    start=max(0,(p-240)&~3)
    end=min(len(code),(p+190)&~3)
    engine=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    instructions=list(engine.disasm(code[start:end],base+start))
    register_ptrs={}
    ptr_access=[]
    for ins in instructions:
        p=ins.address-base
        word=u32(code,p)
        adrp=decode_adrp(word,ins.address)
        if adrp:
            page,reg=adrp
            register_ptrs[reg]={"page":page,"defined_at":ins.address}
            continue
        add=decode_add(word)
        if add:
            rn,rd,displacement=add
            parent=register_ptrs.get(rn)
            if parent and 0 <= ins.address-parent["defined_at"]<=96:
                va=parent["page"]+displacement
                register_ptrs[rd]={"page":parent["page"],"defined_at":ins.address,"va":va}
                info=referenced_data(sections,va)
                ptr_access.append({"register":f"x{rd}",
                                   "adrp_pc":parent["defined_at"],
                                   "add_pc":ins.address,**info})
    hashreg=u32(code,second-base)&31
    writes=[]
    for ins in instructions:
        if ins.address<second or ins.address>second+48:continue
        regs=parse_stp_registers(ins)
        if not regs:continue
        a,b,mem=regs
        writes.append({"pc":ins.address,"op_str":ins.op_str,
                       "first":a,"second":b,"base_reg":mem})
    hash_stores=[x for x in writes if x["first"]==f"w{hashreg}" or x["second"]==f"w{hashreg}"]
    paired=[]
    for s in hash_stores:
        for ptr in writes:
            if ptr["pc"]>s["pc"] and ptr["pc"]-s["pc"]<=24 and ptr["base_reg"]==s["base_reg"] and ptr["first"].startswith("x"):
                paired.append({"hash_write_pc":s["pc"],
                               "pointer_write_pc":ptr["pc"],
                               "hash_stp":s["op_str"],
                               "pointer_stp":ptr["op_str"],
                               "pointer_pair":[ptr["first"],ptr["second"]],
                               "shared_memory_base":f"x{s['base_reg']}"})
    linked_ptrs=[]
    for pair in paired:
        names=set(pair["pointer_pair"])
        # Only take pointer assignments before the paired store, not after it.
        linked_ptrs.extend(x for x in ptr_access if x["register"] in names and
                           x["add_pc"]<pair["pointer_write_pc"] and
                           pair["pointer_write_pc"]-x["add_pc"]<=512)
    # Raw register assignments here are NOT global dataflow: a register might
    # be overwritten inside the window, so paired strings stay candidates.
    disasm=[{"pc":f"0x{i.address:x}","mnemonic":i.mnemonic,"operands":i.op_str}
            for i in instructions]
    return {"hash":candidate["hash"],"movz_pc":first,"movk_pc":second,
            "hash_register":f"w{hashreg}",
            "hash_register_write_sites":hash_stores,
            "paired_descriptor_writes":paired,
            "rodata_pointer_assignments":linked_ptrs,
            "any_verified_hash_memory_store":bool(hash_stores),
            "adjacent_descriptor_pair_proven":bool(paired),
            "semantic_property_name_verified":False,
            "runtime_property_lookup_verified":False,
            "scene_quest_building_text_fk_verified":False,
            "evidence_level":"AARCH64_HASH_REGISTER_STORE_STRUCTURAL",
            "disassembly":disasm}

def analyze(main,prior):
    kind,parts=get_sections(main)
    if kind!="NSO0":raise ValueError("Expected original ExeFS NSO0 main")
    code=next(x for x in parts if x["name"]=="text")
    records=[trace_descriptor_site(code["data"],code["mem_offset"],parts,x)
             for x in prior["arm64_immediate_candidates"]]
    return {
      "status":"M9_CODE_LEVEL_HASH_WRITES_NOT_FIELD_ACCESSORS",
      "main_sha256":hashlib.sha256(main).hexdigest(),
      "inspected_hash_constructor_sites":len(records),
      "hash_sites_with_explicit_memory_store":sum(bool(x["hash_register_write_sites"]) for x in records),
      "hash_sites_with_paired_descriptor_store":sum(x["adjacent_descriptor_pair_proven"] for x in records),
      "records":records,
      "actual_kidsobjdb_property_accessor_verified":0,
      "verified_scene_quest_building_text_foreign_keys":0,
      "notes":[
       "MOVZ/MOVK followed by STP writes reconstructs and stores the literal hash at a code site.",
       "A nearby STP of pointers does not prove that the pointed string is a KIDSOBJDB property name.",
       "IRNK name resources are absent from this repo's currently indexed sources.",
       "Recover basic block, registers and real runtime lookup call before promoting to typed consumer or text FK."
      ]}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main",type=Path,required=True)
    ap.add_argument("--probe",type=Path,required=True)
    ap.add_argument("--dest",type=Path,required=True)
    args=ap.parse_args()
    prior=json.loads(args.probe.read_text(encoding="utf-8"))
    data=args.main.read_bytes()
    if hashlib.sha256(data).hexdigest()!=prior["original_exefs_sha256"]:
        raise ValueError("ExeFS hash changed")
    result=analyze(data,prior)
    args.dest.mkdir(parents=True,exist_ok=True)
    (args.dest/"exefs_descriptor_hash_writes.json").write_text(
      json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    cols=["hash","movz_pc","movk_pc","hash_register",
          "any_verified_hash_memory_store","adjacent_descriptor_pair_proven",
          "paired_descriptor_writes_json","rodata_pointer_assignments_json",
          "semantic_property_name_verified","runtime_property_lookup_verified"]
    with (args.dest/"exefs_descriptor_hash_writes.csv").open("w",encoding="utf-8",newline="") as file:
        out=csv.DictWriter(file,fieldnames=cols)
        out.writeheader()
        for rec in result["records"]:
            out.writerow({"hash":rec["hash"],"movz_pc":rec["movz_pc"],"movk_pc":rec["movk_pc"],
                          "hash_register":rec["hash_register"],
                          "any_verified_hash_memory_store":int(rec["any_verified_hash_memory_store"]),
                          "adjacent_descriptor_pair_proven":int(rec["adjacent_descriptor_pair_proven"]),
                          "paired_descriptor_writes_json":json.dumps(rec["paired_descriptor_writes"],ensure_ascii=False),
                          "rodata_pointer_assignments_json":json.dumps(rec["rodata_pointer_assignments"],ensure_ascii=False),
                          "semantic_property_name_verified":0,
                          "runtime_property_lookup_verified":0})
    print(json.dumps({k:result[k] for k in ("status","inspected_hash_constructor_sites",
        "hash_sites_with_explicit_memory_store","hash_sites_with_paired_descriptor_store",
        "actual_kidsobjdb_property_accessor_verified")},indent=2))

if __name__=="__main__":main()
