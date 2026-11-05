#!/usr/bin/env python3
"""M9.11: instruction windows and native data context for vptr candidates.

Requires exact M9.10 ADRP/ADD source words and ExeFS SHA. Possible stores
and surrounding indirect call instructions are *unverified hypotheses*.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_rnk_exefs_xrefs import decode_adrp,decode_add

MAIN_SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
COLS=("property_hash","adrp_pc","address_pc","address_point","adrp_add_bytes_confirmed",
      "candidate_store_instructions","verified_vptr_store","verified_indirect_call",
      "verified_kidsobjdb_getter","verified_text_fk")


def u32(data,off):
    return struct.unpack_from("<I",data,off)[0]


def inspect_site(code,base,section,record,radius_before=0x80,radius_after=0xe0):
    from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
    pc=int(record["adrp_pc"])
    other=int(record["consumer_pc"])
    off=pc-base
    if not 0<=off<len(code)-4 or not 0<=other-base<len(code)-4:
        raise ValueError("Code address outside verified text section")
    word=u32(code,off)
    word2=u32(code,other-base)
    if f"{word:08x}"!=record["adrp_word"] or f"{word2:08x}"!=record["consumer_word"]:
        raise ValueError("M9.10 instruction byte provenance changed")
    adrp=decode_adrp(word,pc)
    add=decode_add(word2)
    if (adrp is None or add is None or add[0]!=adrp[1]
        or adrp[0]+add[2]!=int(record["address_point"])
        or record["instruction_kind"]!="ADRP_ADD_ADDRESS"):
        raise ValueError("M9.10 ADRP+ADD address did not reconstruct")
    start=max(0,(off-radius_before)&~3)
    end=min(len(code),(other-base+radius_after)&~3)
    cs=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    instructions=[
        {"pc":i.address,"mnemonic":i.mnemonic,"operands":i.op_str}
        for i in cs.disasm(code[start:end],base+start)]
    destination=f"x{add[1]}"
    after=[i for i in instructions if other<i["pc"]<=other+0x70]
    # A store using an address-bearing register is not a verified vptr store:
    # instructions/branches in between may have clobbered the register.
    stores=[i for i in after if i["mnemonic"] in ("str","stp","stur") and
            i["operands"].split(",")[0].strip()==destination]
    blrs=[i for i in after if i["mnemonic"] in ("blr","br")]
    data_bytes=section["data"]
    physical_address=int(record["address_point"])
    pos=physical_address-section["mem_offset"]
    context=[]
    if 0<=pos<len(data_bytes):
        start_data=max(0,(pos-48)//8*8)
        end_data=min(len(data_bytes),(pos+56)//8*8)
        context=[
            {"va":section["mem_offset"]+j,
             "value":f"0x{struct.unpack_from('<Q',data_bytes,j)[0]:016x}"}
            for j in range(start_data,end_data,8) if j+8<=len(data_bytes)
        ]
    return {
        "property_hash":record["property_hash"],
        "adrp_pc":pc, "address_pc":other,
        "address_point":physical_address,
        "destination_register_candidate":destination,
        "adrp_add_bytes_confirmed":True,
        "candidate_store_instructions":stores,
        "nearby_indirect_branch_instructions":blrs,
        "data_qword_context":context,
        "instruction_window":instructions,
        "verified_vptr_store":False,
        "verified_indirect_call":False,
        "verified_kidsobjdb_getter":False,
        "verified_text_fk":False,
        "evidence_grade":"ORIGINAL_ADRP_ADD_AND_CONTEXT_BYTES_ONLY",
    }


def analyze(binary,previous):
    sha=hashlib.sha256(binary).hexdigest()
    if sha!=MAIN_SHA or previous["report"].get("original_exefs_sha256")!=sha:
        raise ValueError("Original ExeFS SHA changed")
    kind,sections=get_sections(binary)
    if kind!="NSO0":raise ValueError("Expected NSO0")
    code=next(x for x in sections if x["name"]=="text")
    data=next(x for x in sections if x["name"]=="data")
    refs=previous["xrefs"]
    if not refs:
        raise ValueError("No M9.10 native addresses; refuse ungrounded scan")
    details=[inspect_site(code["data"],code["mem_offset"],data,r)
             for r in refs if r["instruction_kind"]=="ADRP_ADD_ADDRESS"]
    report={
        "status":"M9_NATIVE_VPTR_XREF_DISASSEMBLY_CONTEXT_ONLY",
        "original_exefs_sha256":sha,
        "verified_native_address_constructions":len(details),
        "possible_destination_stores_nearby":sum(len(d["candidate_store_instructions"]) for d in details),
        "possible_indirect_branch_instructions_nearby":sum(len(d["nearby_indirect_branch_instructions"]) for d in details),
        "verified_vtable_address_point_ownership":0,
        "verified_object_constructor_vptr_store":0,
        "verified_indirect_callback_dispatch":0,
        "verified_kidsobjdb_field_accessor":0,
        "new_scene_quest_building_text_foreign_keys":0,
        "limitations":[
            "A store near ADRP/ADD can be to an unrelated object; no cross-branch register flow is proven.",
            "Nearby BLR/BR is not linked to the address-point without caller and object identity.",
            "A confirmed constructor would still not prove access to M7 or a script field.",
        ],
    }
    return report,details


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    a=p.parse_args()
    report,details=analyze(a.main.read_bytes(),json.loads(a.source.read_text(encoding="utf-8")))
    a.dest.mkdir(parents=True,exist_ok=True)
    (a.dest/"exefs_vptr_disassembly_windows.json").write_text(
        json.dumps({"report":report,"sites":details},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (a.dest/"exefs_vptr_disassembly_sites.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=COLS);w.writeheader()
        for row in details:
            w.writerow({k:json.dumps(row[k],ensure_ascii=False) if isinstance(row[k],list) else row[k] for k in COLS})
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
