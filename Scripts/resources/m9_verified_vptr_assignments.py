#!/usr/bin/env python3
"""M9.12: verify original ARM64 object-vptr writes and callback table slots.

Proof: same-register ADRP+ADD+ADD -> STP X8, XZR,[object],
original bytes and .data vtable contents. This does NOT prove a runtime
indirect call, KIDSOBJDB getter, script text FK or property name semantics.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_rnk_exefs_xrefs import decode_adrp,decode_add

EXPECTED_SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
CHAINS=(
    {"id":"candidate_object_A","adrp_pc":0xD591B8,"add_pc":0xD591BC,
     "final_add_pc":0xD591C4,"store_pc":0xD591C8,
     "source_object_reg":"x23","vptr":0x32FDFA0,
     "descriptor_slot":0x32FDFD8,"callback":0xD59420,"hash":"0xf92c5190"},
    {"id":"neighbor_object_B","adrp_pc":0xD5962C,"add_pc":0xD59630,
     "final_add_pc":0xD5963C,"store_pc":0xD59640,
     "source_object_reg":"x22","vptr":0x32FE0C8,
     "descriptor_slot":None,"callback":None,"hash":None},
)


def u32(data,off):
    return struct.unpack_from("<I",data,off)[0]


def reconstruct_address(code,base,chain):
    pcs=(chain["adrp_pc"],chain["add_pc"],chain["final_add_pc"])
    if any((pc-base)<0 or (pc-base+4)>len(code) for pc in pcs):
        raise ValueError("ARM64 instruction outside source text")
    w0,w1,w2=(u32(code,pc-base) for pc in pcs)
    adrp=decode_adrp(w0,pcs[0])
    first=decode_add(w1)
    second=decode_add(w2)
    if not adrp or not first or not second:
        raise ValueError("Native ARM64 constructor address formation missing")
    # Registers must stay x8 throughout, and only the two known adds write x8.
    if adrp[1]!=8 or first[0]!=8 or first[1]!=8 or second[0]!=8 or second[1]!=8:
        raise ValueError("Native vptr x8 register chain changed")
    return adrp[0]+first[2]+second[2]


def read_pointer(section,va):
    off=va-section["mem_offset"]
    if off<0 or off+8>len(section["data"]):
        raise ValueError("Native vtable pointer outside .data")
    return struct.unpack_from("<Q",section["data"],off)[0]


def verify_one(code,base,data,chain,previous):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    relevant=[
        x for x in previous["sites"]
        if x["adrp_pc"]==chain["adrp_pc"] and x["address_pc"]==chain["add_pc"]
    ]
    if len(relevant)!=1 or not relevant[0]["adrp_add_bytes_confirmed"]:
        raise ValueError("M9.11 proven original ADRP/ADD source missing")
    got=reconstruct_address(code,base,chain)
    if got!=chain["vptr"]:
        raise ValueError(f"Native vptr address mismatch {got:#x} != {chain['vptr']:#x}")
    first=chain["adrp_pc"]
    last=chain["store_pc"]
    cs=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    instructions=list(cs.disasm(code[first-base:last-base+4],first))
    if len(instructions)!=(last-first)//4+1:
        raise ValueError("Native constructor disassembly incomplete")
    bypc={i.address:i for i in instructions}
    for key in ("adrp_pc","add_pc","final_add_pc","store_pc"):
        if chain[key] not in bypc:
            raise ValueError(f"Native instruction absent at {chain[key]:#x}")
    if not (bypc[chain["adrp_pc"]].mnemonic=="adrp" and
            bypc[chain["add_pc"]].mnemonic=="add" and
            bypc[chain["final_add_pc"]].mnemonic=="add"):
        raise ValueError("Native instruction chain mnemonics changed")
    store=bypc[chain["store_pc"]]
    expected=f"x8, xzr, [{chain['source_object_reg']}]"
    if store.mnemonic!="stp" or store.op_str!=expected:
        raise ValueError(f"Native vptr assignment changed: {store.mnemonic} {store.op_str}")
    # No indirect branches, direct branches or unaccounted writes to x8
    # may intervene in the exact positive-path instruction sequence.
    for inst in instructions[1:-1]:
        if inst.mnemonic.startswith(("b","ret","cb","tb")):
            raise ValueError("Native constructor register path crosses a branch")
        if inst.address not in (chain["add_pc"],chain["final_add_pc"]):
            if inst.op_str.split(",")[0].strip() in ("x8","w8"):
                raise ValueError("Intervening x8 write invalidates vptr proof")
    obj={
        "site":chain["id"],"adrp_pc":first,"store_pc":last,
        "object_register":chain["source_object_reg"],
        "written_pointer":got,"store_instruction":store.mnemonic+" "+store.op_str,
        "verified_original_arm64_vptr_assignment":True,
        "verified_runtime_indirect_dispatch":False,
        "verified_kidsobjdb_getter":False,
        "verified_script_text_fk":False,
        "step_instructions":[{"pc":i.address,"mnemonic":i.mnemonic,"op_str":i.op_str}
                             for i in instructions],
    }
    if chain["descriptor_slot"] is not None:
        offset=chain["descriptor_slot"]-got
        if offset<0 or offset % 8:
            raise ValueError("Descriptor callback offset is invalid")
        actual=read_pointer(data,got+offset)
        if actual!=chain["callback"] or offset!=0x38:
            raise ValueError("Native descriptor callback slot content mismatch")
        obj.update({
            "verified_callback_pointer_at_vptr_offset":True,
            "vtable_callback_offset":offset,
            "table_callback_pc":actual,
            "associated_descriptor_hash_candidate":chain["hash"],
        })
    else:
        obj["verified_callback_pointer_at_vptr_offset"]=False
    return obj


def analyze(main,previous):
    sha=hashlib.sha256(main).hexdigest()
    if sha!=EXPECTED_SHA or previous["report"]["original_exefs_sha256"]!=sha:
        raise ValueError("Original ExeFS 2.0.1 provenance mismatch")
    kind,sections=get_sections(main)
    if kind!="NSO0":raise ValueError("Expected native NSO0 main")
    text=next(x for x in sections if x["name"]=="text")
    data=next(x for x in sections if x["name"]=="data")
    rows=[verify_one(text["data"],text["mem_offset"],data,c,previous)
          for c in CHAINS]
    report={
        "status":"M9_NATIVE_OBJECT_VPTR_STORE_AND_CALLBACK_SLOT_VERIFIED",
        "original_exefs_sha256":sha,
        "original_vptr_stores_verified":len(rows),
        "descriptor_callback_table_slots_verified":sum(x["verified_callback_pointer_at_vptr_offset"] for x in rows),
        "verified_runtime_indirect_dispatchers":0,
        "verified_native_kidsobjdb_getters":0,
        "verified_scene_quest_building_m7_text_foreign_keys":0,
        "evidence_grade":"ORIGINAL_ARM64_REGISTER_FLOW_AND_VTABLE_POINTER_BYTES",
        "limitations":[
            "Vptr write and callback slot membership are proven for one original native class; its semantic type is unknown.",
            "There is no demonstrated runtime BLR through that vptr+0x38 to the callback.",
            "Object field getter and script/text foreign key remain unverified.",
        ],
    }
    return report,rows


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--main",type=Path,required=True)
    ap.add_argument("--m9-11",type=Path,required=True)
    ap.add_argument("--dest",type=Path,required=True)
    args=ap.parse_args()
    report,rows=analyze(args.main.read_bytes(),json.loads(args.m9_11.read_text(encoding="utf-8")))
    args.dest.mkdir(parents=True,exist_ok=True)
    (args.dest/"exefs_verified_vptr_stores.json").write_text(
        json.dumps({"report":report,"verified_stores":rows},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
