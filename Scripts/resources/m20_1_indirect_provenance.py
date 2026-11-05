#!/usr/bin/env python3
"""M20.1: inspect exact rodata property hash neighborhood and 17 native item callers.

All associations remain candidate-only. Never infer that 00983 record offsets
are the same in-memory structure as a queried object without loader proof.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import struct

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    SHA_MAIN, SHA_ITEM, MAIN, ITEM, POKEMON_OUT, ITEM_OUT, WRAPPER,
    branch_target, decode_adrp, arm64_window, u32,
)

LITERAL_VA=0x2830C98
PROPERTY=0x2856A1B3
POKEMON_M20=POKEMON_OUT/"m20_original_property_hash_sites.json"
ITEM_M20=ITEM_OUT/"m20_two_stage_item_callers.json"
OFFSETS=(0x0c,0x14,0x18,0x1e,0x26,0x27,0x3a,0x41)
OUTPUT_FIELDS=("caller_pc","has_return_wrapper_plus8","post_call_offset_accesses",
               "post_call_instructions_scanned","grade","original_exefs_sha256")
MEMORY=re.compile(r"\[(x\d+),\s*#0x([0-9a-f]+)\]",re.I)


def neighborhood(main: bytes):
    if hashlib.sha256(main).hexdigest()!=SHA_MAIN:
        raise ValueError("ExeFS is not the verified Pokopia 2.0.1 original")
    kind,sections=get_sections(main)
    if kind!="NSO0":
        raise ValueError("Original input must be NSO0")
    ro=next(s for s in sections if s["name"]=="rodata")
    code=next(s for s in sections if s["name"]=="text")
    off=LITERAL_VA-ro["mem_offset"]
    if off<0 or off+4>len(ro["data"]) or u32(ro["data"],off)!=PROPERTY:
        raise ValueError("Exact native hash literal is absent at 0x2830c98")
    low=max(0,(off-0xc0)&~3)
    high=min(len(ro["data"])&~3,(off+0xc4)&~3)
    words=[{"va":hex(ro["mem_offset"]+p),"u32_le":f"{u32(ro['data'],p):08x}"}
           for p in range(low,high,4)]
    pointer_cells=[]
    for s in sections:
        if s["name"] not in ("rodata","data"):
            continue
        b=s["data"]
        for p in range(0,len(b)-7,8):
            val=struct.unpack_from("<Q",b,p)[0]
            if LITERAL_VA-0x100<=val<=LITERAL_VA+0x100:
                pointer_cells.append({
                    "pointer_cell_va":hex(s["mem_offset"]+p),
                    "pointer_value":hex(val),"section":s["name"],
                    "offset_from_property":val-LITERAL_VA,
                    "grade":"STATIC_POINTER_VALUE_ONLY"})
    buf,base=code["data"],code["mem_offset"]
    page=LITERAL_VA & ~0xfff
    page_refs=[]
    effective=[]
    for p in range(0,len(buf)-3,4):
        pc=base+p
        decoded=decode_adrp(u32(buf,p),pc)
        if not decoded or decoded[0]!=page:
            continue
        page_refs.append(hex(pc))
        reg=decoded[1]
        for delta in range(4,37,4):
            q=p+delta
            if q+4>len(buf):
                break
            w=u32(buf,q)
            if (w&0xff000000)==0x91000000 and ((w>>5)&31)==reg:
                shift=(w>>22)&3
                if shift>1:continue
                va=page+(((w>>10)&0xfff)<<(12 if shift else 0))
                kind="ADD_ADDRESS"
            elif (w&0xffc00000)==0xb9400000 and ((w>>5)&31)==reg:
                va=page+(((w>>10)&0xfff)*4)
                kind="LDR_W"
            elif (w&0xffc00000)==0xf9400000 and ((w>>5)&31)==reg:
                va=page+(((w>>10)&0xfff)*8)
                kind="LDR_X"
            else:
                continue
            if abs(va-LITERAL_VA)>0x100:
                continue
            effective.append({
                "adrp_pc":hex(pc),"second_pc":hex(base+q),
                "computed_address":hex(va),"distance_to_hash":va-LITERAL_VA,
                "kind":kind,"instruction_gap":delta//4,
                "grade":"EXACT_NEARBY_NATIVE_ADDRESS__SEMANTICS_UNPROVEN"})
    return {
        "status":"M20_1_EXACT_HASH_RODATA_NEIGHBORHOOD__PROPERTY_UNBOUND",
        "main_sha256":SHA_MAIN,"hash":f"0x{PROPERTY:08x}",
        "original_hash_cell_va":hex(LITERAL_VA),
        "rodata_u32_neighborhood":words,
        "nearby_pointer_cells":pointer_cells[:200],
        "nearby_pointer_cells_total":len(pointer_cells),
        "code_adrp_same_page_total":len(page_refs),
        "code_adrp_same_page_first":page_refs[:100],
        "nearby_effective_address_sites_total":len(effective),
        "nearby_effective_address_sites_first":effective[:100],
        "nearby_code_windows":[
            {"pc":r["second_pc"],
             "instructions":arm64_window(buf,base,int(r["second_pc"],16),0x20,0x48)}
            for r in effective[:32]
        ],
        "native_property_consumer_verified":False,
        "native_species_id_verified":False,
        "warning":"Data adjacency, page references and static pointer cells do not prove object identity or property consumer."
    }


def caller_field_matrix(m20: dict):
    if m20.get("original_main_sha256")!=SHA_MAIN or m20.get("two_stage_wrapper_pc")!=hex(WRAPPER):
        raise ValueError("Stale original two-stage caller evidence")
    if m20["direct_BL_callers_total"]!=17:
        raise ValueError("Original wrapper caller count changed; review source first")
    results=[]
    for row in m20["caller_instruction_windows"]:
        if row["call_kind"]!="BL":continue
        p=row["caller_pc"]
        rows=row["instructions"]
        match=next((i for i,x in enumerate(rows) if x["pc"]==p),None)
        if match is None or not rows[match]["asm"].startswith("bl #0x2f1f0"):
            raise ValueError("Not a direct native wrapper BL instruction")
        following=rows[match+1:match+25]
        wrap=any(re.search(r"\bldr x\d+, \[x0, #8\]",x["asm"]) for x in following)
        offsets=[]
        for ins in following:
            m=MEMORY.search(ins["asm"])
            if not m:continue
            off=int(m.group(2),16)
            if off not in OFFSETS:continue
            if ins["asm"].split()[0] not in ("ldr","ldrb","ldrh","ldurh","ldur","ldurb"):
                continue
            offsets.append(f"{ins['pc']}:{ins['asm']}")
        results.append({
            "caller_pc":p,
            "has_return_wrapper_plus8":int(wrap),
            "post_call_offset_accesses":" | ".join(offsets),
            "post_call_instructions_scanned":len(following),
            "grade":"BOUNDED_ORIGINAL_INSTRUCTION_WINDOW__POINTER_DATAFLOW_UNPROVEN",
            "original_exefs_sha256":SHA_MAIN
        })
    if len(results)!=17:
        raise ValueError("Dropped original wrapper callsites")
    return results


def native_distributions(item:bytes):
    if hashlib.sha256(item).hexdigest()!=SHA_ITEM:
        raise ValueError("Not original 2.0.1 00983.bin")
    if len(item)!=64+4600*68:
        raise ValueError("Not native 4600x68 item records")
    hist={}
    for off in OFFSETS:
        if off>=68:raise ValueError("Invalid native field offset")
        c=Counter(item[64+i*68+off] for i in range(4600))
        hist[f"0x{off:02x}"]={
            "raw_byte_distinct_count":len(c),
            "raw_byte_top_values":[{"value":v,"count":n} for v,n in c.most_common(20)],
            "records":4600,"original_record_stride":68,
            "proven_same_memory_as_wrapper_plus8":False,
            "semantic_enum_verified":False}
    return {
        "status":"M20_1_ORIGINAL_00983_OFFSET_DISTRIBUTIONS_ONLY",
        "source_sha256":SHA_ITEM,
        "fields":hist,
        "warning":"Numerical similarity does not bind 00983 offsets to the queried runtime pointer."}


def selftest():
    example={"original_main_sha256":SHA_MAIN,"two_stage_wrapper_pc":hex(WRAPPER),
             "direct_BL_callers_total":17,"caller_instruction_windows":[]}
    try:caller_field_matrix(example)
    except ValueError:pass
    else:raise AssertionError("Accepted absent native caller records")
    try:native_distributions(b"forged")
    except ValueError:pass
    else:raise AssertionError("Accepted forged original item records")
    assert branch_target(0x1000,0x94000400)==(0x2000,"BL")
    print("PASS original-byte and 17-caller provenance guards")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.self_test:
        selftest()
        return
    main_bytes=MAIN.read_bytes()
    item_bytes=ITEM.read_bytes()
    prior_p=json.loads(POKEMON_M20.read_text(encoding="utf-8"))
    prior_i=json.loads(ITEM_M20.read_text(encoding="utf-8"))
    if prior_p.get("original_main_sha256")!=SHA_MAIN or prior_p.get("property_hash")!=f"0x{PROPERTY:08x}":
        raise ValueError("Stale source for original property hash literal")
    if prior_p.get("literal_cells_total")!=1 or prior_p["literal_cells_first"][0]["va"]!=hex(LITERAL_VA):
        raise ValueError("Property hash position differs from certified M20")
    prop=neighborhood(main_bytes)
    matrix=caller_field_matrix(prior_i)
    distributions=native_distributions(item_bytes)
    POKEMON_OUT.mkdir(parents=True,exist_ok=True)
    ITEM_OUT.mkdir(parents=True,exist_ok=True)
    (POKEMON_OUT/"m20_1_rodata_hash_neighborhood.json").write_text(json.dumps(prop,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ITEM_OUT/"m20_1_native_item_offset_distributions.json").write_text(json.dumps(distributions,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (ITEM_OUT/"m20_1_original_wrapper_caller_offsets.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=OUTPUT_FIELDS)
        w.writeheader()
        w.writerows(matrix)
    print(json.dumps({
       "original_rodata_literal_va":hex(LITERAL_VA),
       "rodata_pointer_cells_nearby":prop["nearby_pointer_cells_total"],
       "same_page_adrp":prop["code_adrp_same_page_total"],
       "effective_address_sites_within_0x100":prop["nearby_effective_address_sites_total"],
       "native_item_direct_callers":len(matrix),
       "callers_with_wrapper_plus8":sum(x["has_return_wrapper_plus8"] for x in matrix),
       "semantic_species_ids_proven":0,"material_enum_proven":False
    },indent=2))


if __name__=="__main__":
    main()
