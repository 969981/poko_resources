#!/usr/bin/env python3
"""M9.19: specific two callback-table virtual address points and owner x3.

The only source entries are M9.18's exact original .data pointer slots:
 cleanup 0x32fde38 -> main+0xd58e34
 create  0x32fdf38 -> main+0xd590e0
Test a focused *hypothesis* that both occupy vptr+0x38. Scan source
ARM64 ADRP+ADD/ADRP+ADD+ADD references to just those two derived address
points and inspect bounded source instructions. A byte match is not a
proven object vptr assignment or a proven owner x3 caller.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_rnk_exefs_xrefs import decode_adrp, decode_add

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
KNOWN={
    "owner_cleanup_callback":(0x32FDE38,0xD58E34),
    "owner_constructor_callback":(0x32FDF38,0xD590E0),
}
VTABLE_OFFSET_HYPOTHESIS=0x38
MAX_REF_ROWS=300


def u32(blob,off):return struct.unpack_from("<I",blob,off)[0]
def u64(blob,off):return struct.unpack_from("<Q",blob,off)[0]


def data_pointer(data,slot):
    off=slot-data["mem_offset"]
    if not 0<=off<=len(data["data"])-8:raise ValueError(f"Unmapped .data slot {slot:#x}")
    return u64(data["data"],off)


def derived_base_candidates(data):
    result=[]
    for name,(slot,entry) in KNOWN.items():
        if data_pointer(data,slot)!=entry:
            raise ValueError(f"Original M9.18 callback entry byte mismatch {name}")
        va=slot-VTABLE_OFFSET_HYPOTHESIS
        slot0=data_pointer(data,va)
        result.append({
            "function":name,"known_callback_slot_va":slot,"known_callback_pc":entry,
            "hypothesized_vptr":va,"hypothesized_slot_offset":VTABLE_OFFSET_HYPOTHESIS,
            "vptr_slot0_qword":slot0,
            "slot0_in_native_executable_range":0<=slot0<0x2749c00,
            "callback_at_derived_vptr_plus_0x38_exact":data_pointer(data,va+0x38)==entry,
            "proven_vptr":False,"proven_same_owner_class":False,
        })
    return result


def scan_specific_adrp(code,base,target_addresses,max_output=MAX_REF_ROWS):
    # This is deliberately NOT a global BLR search. Only reconstruct
    # specific address projections from two known callback slots.
    targetset=set(target_addresses)
    pages={x>>12 for x in targetset}
    result=[]
    count=Counter()
    for pos in range(0,len(code)-3,4):
        pc=base+pos
        dec=decode_adrp(u32(code,pos),pc)
        if dec is None or dec[0]>>12 not in pages:continue
        page,r0=dec
        for delta in (4,8,12,16,20,24,28,32):
            if pos+delta+4>len(code):break
            op=decode_add(u32(code,pos+delta))
            if not op or op[0]!=r0:continue
            addr=page+op[2]
            if addr in targetset:
                count[addr]+=1
                if len(result)<max_output:
                    result.append({
                        "adrp_pc":pc,"add_pc":pc+delta,"constructed_data_va":addr,
                        "written_register":f"x{op[1]}","distance_instructions":delta//4,
                        "source_words":[f"{u32(code,pos):08x}",f"{u32(code,pos+delta):08x}"],
                        "evidence_grade":"EXACT_ADRP_ADD_VALUE" if delta==4
                          else "NONADJACENT_ADRP_ADD_VALUE_CANDIDATE",
                        "object_vptr_store_verified":False,
                    })
            # A known pattern from M9.12 is ADD x8,x8,#imm + ADD x8,x8,#0x10.
            # Check a second immediately adjacent ADD that is reg-flow intact.
            if op[1]!=r0 or pos+delta+8>len(code):continue
            nxt=decode_add(u32(code,pos+delta+4))
            if nxt and nxt[0]==r0 and nxt[1]==r0:
                second=addr+nxt[2]
                if second in targetset:
                    count[second]+=1
                    if len(result)<max_output:
                        result.append({
                            "adrp_pc":pc,"add_pc":pc+delta,
                            "second_add_pc":pc+delta+4,
                            "constructed_data_va":second,"written_register":f"x{r0}",
                            "distance_instructions":delta//4+1,
                            "source_words":[f"{u32(code,pos):08x}",
                                            f"{u32(code,pos+delta):08x}",
                                            f"{u32(code,pos+delta+4):08x}"],
                            "evidence_grade":"TWO_ADD_SAME_REGISTER_VALUE_CANDIDATE",
                            "object_vptr_store_verified":False,
                        })
    return result,dict(count)


def source_context(code,base,rows):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    cs=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    for row in rows:
        off=row["adrp_pc"]-base
        start=max(0,(off-0x20)&~3)
        end=min(len(code),off+0x90)
        row["nearby_instructions"]=[
            {"pc":i.address,"mnemonic":i.mnemonic,"op":i.op_str}
            for i in cs.disasm(code[start:end],base+start)]
        # Same-address target vptr not yet confirmed: 'STR' may use clobbered register.
        row["nearby_struct_pointer_writes"]=[
            i for i in row["nearby_instructions"] if i["mnemonic"] in ("str","stp","stur")
            and i["op"].split(",")[0]==row["written_register"]]
    return rows


def analyze(main,previous):
    sha=hashlib.sha256(main).hexdigest()
    if sha!=SHA or previous["report"]["source_exefs_sha256"]!=sha:
        raise ValueError("Original NSO or M9.18 callback table provenance differs")
    hits={h["function"]:(h["pointer_data_va"],h["callback_entry_pc"])
          for h in previous["data_pointer_xrefs"]}
    if hits!=KNOWN:
        raise ValueError(f"Wrong exact M9.18 caller entries: {hits}")
    fmt,sections=get_sections(main)
    if fmt!="NSO0":raise ValueError("Original NSO0 required")
    data=next(x for x in sections if x["name"]=="data")
    text=next(x for x in sections if x["name"]=="text")
    bases=derived_base_candidates(data)
    point_targets={c["hypothesized_vptr"] for c in bases}
    rows,counts=scan_specific_adrp(text["data"],text["mem_offset"],point_targets)
    source_context(text["data"],text["mem_offset"],rows)
    report={
        "status":"M9_SPECIFIC_TWO_CALLBACK_VPTR_BASE_PROBE",
        "original_exefs_sha256":sha,
        "exact_known_callback_pointer_slots_verified":len(KNOWN),
        "vptr_offset_hypothesis":VTABLE_OFFSET_HYPOTHESIS,
        "derived_address_point_probes":len(bases),
        "specific_target_adrp_add_candidate_rows":sum(counts.values()),
        "rows_saved":len(rows),
        "specific_target_xref_counts_by_va":{hex(k):v for k,v in sorted(counts.items())},
        "confirmed_object_constructor_vptr_assignments":0,
        "confirmed_x3_same_owner_dispatch":0,
        "confirmed_specific_slot0x38_runtime_dispatch":0,
        "KIDSOBJDB_property_getters_verified":0,
        "new_M7_script_text_FKs":0,
        "limitations":[
            "Deriving vptr=callback_slot-0x38 assumes slot placement; pointer byte identity alone does not establish vptr use.",
            "ADRP+ADD exact target is a native address construction but can be for an unrelated purpose.",
            "Nearby STR writes need register-flow and object-class proof, and same owner x3 needs caller identity.",
            "No script or M7 foreign-key promotion from callback or table adjacency.",
        ],
    }
    return {"report":report,"derived_address_point_hypotheses":bases,"code_address_xrefs":rows}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--callback-evidence",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    a=p.parse_args()
    report=analyze(a.main.read_bytes(),json.loads(a.callback_evidence.read_text(encoding="utf-8")))
    a.dest.mkdir(parents=True,exist_ok=True)
    (a.dest/"exefs_owner_callback_vptr_base_probes.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report["report"],ensure_ascii=False,indent=2))


if __name__=="__main__":main()
