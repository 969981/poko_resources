#!/usr/bin/env python3
"""M9.20: inspect only sibling callbacks of M9.18's two proven tables.

Follow exact native .data slot+8,+16,+24,+32,+40 entries adjacent to
cleanup/create callbacks. Decode their own ARM64 bodies and rank *local*
owner x3 / owner+0x28 / vptr+0x38 access candidates; never generalize
virtual call offset matches to unrelated classes. Result is static evidence,
not an observed runtime dispatch or game text foreign key.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_owner_object_escape import ldrx, is_blr_reg

SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ROOTS={
    "cleanup_table":(0x32fde38,0xd58e34),
    "constructor_table":(0x32fdf38,0xd590e0),
}
NEIGHBOR_OFFSETS=(0,8,16,24,32,40)
MAX_INSTRUCTIONS=112


def u32(x,p):return struct.unpack_from("<I",x,p)[0]
def u64(x,p):return struct.unpack_from("<Q",x,p)[0]


def checked_data_ptr(data,va):
    p=va-data["mem_offset"]
    if not 0<=p<=len(data["data"])-8:
        raise ValueError(f"Callback slot unmapped {va:#x}")
    return u64(data["data"],p)


def sibling_table_entries(data,old):
    present={h["function"]:(h["pointer_data_va"],h["callback_entry_pc"])
             for h in old["data_pointer_xrefs"]}
    want={
        "owner_cleanup_callback":ROOTS["cleanup_table"],
        "owner_constructor_callback":ROOTS["constructor_table"],
    }
    if present!=want:raise ValueError("Native M9.18 exact callback pointer slots changed")
    rows=[]
    for table,(root,first) in ROOTS.items():
        if checked_data_ptr(data,root)!=first:
            raise ValueError("Native root callback no longer matches original RDB")
        for delta in NEIGHBOR_OFFSETS:
            target=checked_data_ptr(data,root+delta)
            rows.append({
                "table":table,"data_slot_va":root+delta,
                "relative_to_root_entry":delta,
                "native_function_pc":target,
                "root_entry_verified":delta==0,
                "same_table_neighbor_qword_verified":True,
                "semantic_callback_type_verified":False,
                "runtime_owner_identity_verified":False,
            })
    return rows


def decode_sibling(code,base,row):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    pc=row["native_function_pc"]
    if pc%4 or pc<base or pc>=base+len(code):
        row["decode_status"]="OUTSIDE_OR_UNALIGNED_EXEFS_TEXT"
        row["instruction_window"]=[]
        row["owner_slot38_call_shapes"]=[]
        return row
    start=pc-base
    end=min(len(code),start+4*MAX_INSTRUCTIONS)
    cs=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    rows=[]
    for inst in cs.disasm(code[start:end],pc):
        rows.append({"pc":inst.address,"op":inst.mnemonic,"args":inst.op_str,
                     "u32":f"{u32(code,inst.address-base):08x}"})
        if inst.mnemonic in ("ret","retab","br") and len(rows)>1:
            break
        # Unconditional direct B is a forwarding thunk, and native text
        # beyond the branch is not the current method's linear fallthrough.
        if inst.mnemonic=="b" and len(rows)>1:
            break
    row["decode_status"]="NATIVE_ORIGINAL_INSTRUCTION_WINDOW"
    row["instruction_window"]=rows
    row["x3_alias_mov_sites"]=[r for r in rows if r["op"]=="mov" and r["args"].endswith(", x3")]
    row["owner_member_0x28_reads"]=[
        {"pc":r["pc"],**ldrx(int(r["u32"],16))}
        for r in rows if r["op"]=="ldr" and ldrx(int(r["u32"],16))
        and ldrx(int(r["u32"],16))["offset"]==0x28]
    checks=[]
    for n,p in enumerate(rows):
        # Restricted to exactly these 12 callback functions. A contiguous
        # LDR(object,[owner+0x28]) / LDR(vptr,[obj]) /
        # LDR(fn,[vptr+0x38]) / BLR(fn) is strong instruction-level shape,
        # but object class identity and runtime target still unproven.
        if n+3>=len(rows):break
        insts=rows[n:n+4]
        a,b,c=(ldrx(int(r["u32"],16)) for r in insts[:3])
        if not(a and b and c):continue
        if a["offset"]!=0x28 or b["base"]!=a["dst"] or b["offset"]!=0:continue
        if c["base"]!=b["dst"] or c["offset"]!=0x38:continue
        if not is_blr_reg(int(insts[3]["u32"],16),c["dst"]):continue
        checks.append({
            "owner_field_pc":insts[0]["pc"],"vptr_load_pc":insts[1]["pc"],
            "callback_load_pc":insts[2]["pc"],"blr_pc":insts[3]["pc"],
            "words":[r["u32"] for r in insts],
            "exact_contiguous_4_instruction_pattern":True,
            "specific_target_class_proven":False,
            "call_observed_at_runtime":False,
        })
    row["owner_slot38_call_shapes"]=checks
    return row


def analyze(main,prior):
    sha=hashlib.sha256(main).hexdigest()
    if sha!=SHA or prior["report"]["source_exefs_sha256"]!=sha:
        raise ValueError("Wrong original ExeFS 2.0.1 source")
    kind,parts=get_sections(main)
    if kind!="NSO0":raise ValueError("Original NSO0 required")
    data=next(s for s in parts if s["name"]=="data")
    code=next(s for s in parts if s["name"]=="text")
    sibs=[decode_sibling(code["data"],code["mem_offset"],r)
          for r in sibling_table_entries(data,prior)]
    report={
        "status":"M9_SPECIFIC_CALLBACK_SIBLING_CODE_TRIAGE",
        "original_exefs_sha256":sha,
        "exact_source_callback_tables":len(ROOTS),
        "exact_neighbor_qword_slots_verified":len(sibs),
        "executable_callback_entry_windows":sum(r["decode_status"]=="NATIVE_ORIGINAL_INSTRUCTION_WINDOW" for r in sibs),
        "sibling_x3_alias_mov_count":sum(len(r.get("x3_alias_mov_sites",[])) for r in sibs),
        "sibling_owner_plus_0x28_ldr_count":sum(len(r.get("owner_member_0x28_reads",[])) for r in sibs),
        "sibling_contiguous_owner_to_slot38_blr_patterns":sum(len(r["owner_slot38_call_shapes"]) for r in sibs),
        "specific_inner_object_vptr_0x32fdfa0_dispatch_proven":0,
        "same_owner_x3_runtime_instance_proven":False,
        "new_KIDSOBJDB_getter_proofs":0,
        "new_script_to_M7_foreign_keys":0,
        "limitations":[
            "Callback table slot adjacency does not prove invocation or inheritance; source register x3 is caller-controlled.",
            "Function bodies are deliberately bounded and stop on direct return/tail branching; out-of-window flows remain open.",
            "Even exact object+0x28 and vptr+0x38 instruction shape needs same owner/class provenance.",
            "No RNK file or localized text foreign key is inferred from callback matching.",
        ],
    }
    return {"report":report,"callbacks":sibs}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--table-evidence",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    a=p.parse_args()
    r=analyze(a.main.read_bytes(),json.loads(a.table_evidence.read_text(encoding="utf-8")))
    a.dest.mkdir(parents=True,exist_ok=True)
    (a.dest/"exefs_owner_sibling_callback_consumers.json").write_text(
        json.dumps(r,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(r["report"],ensure_ascii=False,indent=2))


if __name__=="__main__":main()
