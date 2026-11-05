#!/usr/bin/env python3
"""M20.3: reverse-reference the original 0xce854c function-pointer cell.

Candidate virtual-table neighborhoods are not concrete class or object vptr
bindings. Construction paths require instruction-level register dataflow.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    SHA_MAIN, MAIN, POKEMON_OUT, decode_adrp, arm64_window, u32,
)

CELL=0x32F0EF8
METHOD=0xCE854C
MAX_DIST=0xA0
PRIOR=POKEMON_OUT/"m20_2_original_hash_array_consumer.json"

def span(parts,addr,size):
    for s in parts:
        pos=addr-s["mem_offset"]
        if pos>=0 and pos+size<=len(s["data"]):
            return s["name"],s["data"][pos:pos+size]
    return None,None


def analyze(main:bytes,prior:dict):
    if hashlib.sha256(main).hexdigest()!=SHA_MAIN:
        raise ValueError("Original 2.0.1 ExeFS SHA-256 mismatch")
    if prior.get("original_main_sha256")!=SHA_MAIN or not prior.get("native_schema_hash_array_read_verified"):
        raise ValueError("M20.2 original function-pointer evidence missing")
    pointer_cells=prior.get("raw_function_pointer_cells",[])
    if len(pointer_cells)!=1 or pointer_cells[0]["pointer_cell_va"]!=hex(CELL):
        raise ValueError("Cannot adopt an unverified native function pointer")
    kind,parts=get_sections(main)
    if kind!="NSO0":raise ValueError("Not mapped original NSO0")
    origin,ptr=span(parts,CELL,8)
    if origin!="data" or struct.unpack("<Q",ptr)[0]!=METHOD:
        raise ValueError("Original function-pointer slot contents changed")
    code=next(x for x in parts if x["name"]=="text")
    base=code["mem_offset"];end=base+len(code["data"])
    nearby=[]
    for addr in range(CELL-MAX_DIST,CELL+MAX_DIST+1,8):
        sec,buf=span(parts,addr,8)
        if buf is None:continue
        val=struct.unpack("<Q",buf)[0]
        nearby.append({
            "cell":hex(addr),"value":hex(val),
            "executable_pointer":base+0x100<=val<end and val%4==0,
            "offset_from_method_cell":addr-CELL})
    # An executable pointer run is suggestive of a method table but cannot
    # locate its vptr address or prove its class without constructor stores.
    executable={int(r["cell"],16) for r in nearby if r["executable_pointer"]}
    candidate_starts=[]
    for n in range(0,16):
        addr=CELL-n*8
        before=sum(addr+i*8 in executable for i in range(n+1))
        uninterrupted=all(addr+i*8 in executable for i in range(n+1))
        after=sum(addr+i*8 in executable for i in range(n+1, n+8))
        candidate_starts.append({
            "candidate_table_start":hex(addr),"method_pointer_offset":hex(CELL-addr),
            "executable_pointer_cells_through_method":before,
            "all_entries_to_method_executable":uninterrupted,
            "next_seven_executable_pointer_cells":after,
            "vtable_identity_proven":False})
    low=CELL-MAX_DIST;high=CELL+MAX_DIST
    reverse_raw=[]
    for s in parts:
        if s["name"] not in ("rodata","data"):
            continue
        blob=s["data"]
        for p in range(0,len(blob)-7,8):
            v=struct.unpack_from("<Q",blob,p)[0]
            if low<=v<=high:
                reverse_raw.append({
                    "pointer_cell":hex(s["mem_offset"]+p),
                    "target_near_method_slot":hex(v),
                    "distance_from_method_slot":v-CELL,
                    "constructor_verified":False})
    # ADRP page and immediate ADD/LDR X references to addresses around the
    # pointer cell. The lookahead is bounded, and nonadjacent register liveness
    # is not assumed.
    refs=[]
    samepage=0
    buf=code["data"]
    page=CELL & ~0xfff
    for p in range(0,len(buf)-3,4):
        pc=base+p
        dec=decode_adrp(u32(buf,p),pc)
        if dec is None or dec[0]!=page:
            continue
        samepage+=1
        for delta in range(4,37,4):
            q=p+delta
            if q+4>len(buf):break
            w=u32(buf,q)
            if (w&0xff000000)==0x91000000 and ((w>>5)&31)==dec[1]:
                shift=(w>>22)&3
                if shift>1:continue
                address=page+(((w>>10)&0xfff)<<(12 if shift else 0))
                op="ADD_ADDRESS"
            elif (w&0xffc00000)==0xf9400000 and ((w>>5)&31)==dec[1]:
                address=page+(((w>>10)&0xfff)*8)
                op="LDR_X_CELL"
            else:continue
            if not low<=address<=high:continue
            refs.append({
                "adrp_pc":hex(pc),"second_pc":hex(base+q),
                "computed_addr":hex(address),"offset_from_method_cell":address-CELL,
                "operation":op,"instruction_gap":delta//4,
                "grade":"NEARBY_ADDRESS_XREF__CONSTRUCTOR_UNPROVEN"})
    return {
        "status":"M20_3_NATIVE_METHOD_POINTER_NEIGHBORHOOD__CLASS_UNBOUND",
        "main_sha256":SHA_MAIN,
        "schema_function_entry":hex(METHOD),
        "schema_function_pointer_cell":hex(CELL),
        "native_function_pointer_cell_exact_verified":True,
        "surrounding_pointer_cells":nearby,
        "candidate_table_origins":candidate_starts,
        "native_raw_pointers_to_table_neighborhood":reverse_raw[:200],
        "native_raw_pointers_to_neighborhood_total":len(reverse_raw),
        "adrp_page_references":samepage,
        "nearby_address_xrefs_total":len(refs),
        "nearby_address_xrefs_first":refs[:100],
        "code_windows_first":[
            {"second_pc":r["second_pc"],
             "instructions":arm64_window(buf,base,int(r["second_pc"],16),0x30,0x50)}
            for r in refs[:28]
        ],
        "concrete_schema_vtable_identity_verified":False,
        "schema_class_constructor_verified":False,
        "pokemon_species_id_verified":False,
        "warning":"A raw code pointer in data is not enough to identify vtable base, class, constructor, or species field."
    }

def selftest():
    try:analyze(b"forged",{})
    except ValueError:pass
    else:raise AssertionError("Accepted forged original ExeFS")
    print("PASS source and prior function-pointer verification guards")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:
        selftest();return
    prior=json.loads(PRIOR.read_text(encoding="utf-8"))
    result=analyze(MAIN.read_bytes(),prior)
    POKEMON_OUT.mkdir(parents=True,exist_ok=True)
    (POKEMON_OUT/"m20_3_schema_pointer_backrefs.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "pointer_cell_exact_verified":result["native_function_pointer_cell_exact_verified"],
        "adjacent_executable_pointers":sum(x["executable_pointer"] for x in result["surrounding_pointer_cells"]),
        "raw_pointers_to_table_neighborhood":result["native_raw_pointers_to_neighborhood_total"],
        "adrp_same_page":result["adrp_page_references"],
        "adjacent_address_xrefs":result["nearby_address_xrefs_total"],
        "class_identity_verified":False,"species_ID_verified":False
    },indent=2))

if __name__=="__main__":main()
