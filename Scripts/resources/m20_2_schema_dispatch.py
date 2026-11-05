#!/usr/bin/env python3
"""M20.2 exact three-property array consumer evidence, without species promotion.

The AArch64 code builds an output tuple containing a selected property hash.
This does not establish a native species/form key or how the tuple is used.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    SHA_MAIN, MAIN, POKEMON_OUT, arm64_window, scan_direct_callers, u32,
)

HASH_TABLE=0x2830C90
HASHES=(0xC8BB66DA,0x2276FC56,0x2856A1B3)
FUNCTION=0xCE854C
POINTER_TABLE=0x3330928
CHECK={
    0xCE8554:("cmp w3, #2",),
    0xCE8558:("b.hi ",),
    0xCE855C:("adrp x8,",),
    0xCE8560:("add x8, x8, #0xc90",),
    0xCE8564:("adrp x9,",),
    0xCE8568:("add x9, x9, #0x928",),
    0xCE856C:("ldr w11, [x8, w3, sxtw #2]",),
    0xCE8570:("ldr x12, [x9, w3, sxtw #3]",),
    0xCE8574:("mov w10, #1",),
    0xCE8578:("movk w10, #0x500, lsl #16",),
    0xCE857C:("stp w10, w11, [x1]",),
    0xCE8588:("stp x12, x11, [x1, #8]",),
}

def mapped_bytes(parts,address,length):
    for s in parts:
        off=address-s["mem_offset"]
        if 0<=off and off+length<=len(s["data"]):
            return s["name"],s["data"][off:off+length]
    return None,None


def verify(main:bytes):
    if hashlib.sha256(main).hexdigest()!=SHA_MAIN:
        raise ValueError("Original Pokopia 2.0.1 ExeFS SHA mismatch")
    kind,parts=get_sections(main)
    if kind!="NSO0":
        raise ValueError("Expected original mapped NSO0")
    name,data=mapped_bytes(parts,HASH_TABLE,4*len(HASHES))
    if name!="rodata" or data!=struct.pack("<3I",*HASHES):
        raise ValueError("Exact native three-property hash table changed")
    code=next(x for x in parts if x["name"]=="text")
    buf,base=code["data"],code["mem_offset"]
    win=arm64_window(buf,base,0xCE8570,0x38,0x38)
    asm={int(x["pc"],16):x["asm"] for x in win}
    for pc,words in CHECK.items():
        if pc not in asm or not all(w in asm[pc] for w in words):
            raise ValueError(f"Original schema array consumer changed at {pc:#x}: {asm.get(pc)}")
    # Index w3 is compared against 2; the index-scaled load accesses
    # array base+4*w3. We do not infer arbitrary caller constraints.
    direct,tail=scan_direct_callers(buf,base,FUNCTION)
    refs=[]
    for s in parts:
        if s["name"] not in ("rodata","data"):
            continue
        b=s["data"]
        for off in range(0,len(b)-7,8):
            ptr=struct.unpack_from("<Q",b,off)[0]
            if ptr==FUNCTION:
                refs.append({"pointer_cell_va":hex(s["mem_offset"]+off),
                             "source_section":s["name"],
                             "raw_target_va":hex(ptr),
                             "class_or_vtable_verified":False})
    second_section,second_bytes=mapped_bytes(parts,POINTER_TABLE,24)
    return {
        "status":"ORIGINAL_NATIVE_THREE_PROPERTY_INDEXED_HASH_READ_VERIFIED__SEMANTIC_ROLE_UNBOUND",
        "original_main_sha256":SHA_MAIN,
        "native_hash_array_base":hex(HASH_TABLE),
        "native_hash_array_source_section":name,
        "indexed_property_hashes":[
            {"native_array_index":i,"hash":f"0x{h:08x}",
             "semantic_label":"G1T_RESOURCE_HASH" if i==0 else
             "TEXINFO_RESOURCE_HASH" if i==1 else "UNKNOWN_TYPED_EDGE_TARGET_HASH"}
            for i,h in enumerate(HASHES)
        ],
        "function_entry_candidate":hex(FUNCTION),
        "verified_original_instruction_sequence":win,
        "index_register":"w3", "native_index_upper_bound_constant":2,
        "field_hash_read":"ldr w11, [x8, w3, sxtw #2]",
        "parallel_pointer_array_base_candidate":hex(POINTER_TABLE),
        "parallel_pointer_array_mapped_section":second_section,
        "parallel_pointer_array_raw_bytes_hex":second_bytes.hex() if second_bytes else None,
        "output_hash_write":"stp w10, w11, [x1]",
        "output_following_pointer_write":"stp x12, x11, [x1, #8]",
        "direct_bl_callers_total":len(direct),
        "direct_bl_callers":[hex(x) for x in direct[:100]],
        "direct_b_tail_callers_total":len(tail),
        "direct_b_tail_callers":[hex(x) for x in tail[:100]],
        "raw_function_pointer_cells":refs[:100],
        "raw_function_pointer_cells_total":len(refs),
        "native_schema_hash_array_read_verified":True,
        "native_property_semantic_identity_verified":False,
        "pokemon_species_id_binding_verified":False,
        "warning":"The native function indexes a 3-hash array and writes hash to memory. This is not proof of field name, species ID or runtime use by a specific object."
    }

def selftest():
    bad=bytearray(64)
    try:verify(bytes(bad))
    except ValueError:pass
    else:raise AssertionError("Forged native source accepted")
    assert struct.unpack("<3I",struct.pack("<3I",*HASHES))==HASHES
    print("PASS three-property array layout and fail-closed original source guard")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:
        selftest()
        return
    report=verify(MAIN.read_bytes())
    POKEMON_OUT.mkdir(parents=True,exist_ok=True)
    (POKEMON_OUT/"m20_2_original_hash_array_consumer.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({
        "status":report["status"],
        "original_hash_array_base":report["native_hash_array_base"],
        "native_array_read_verified":report["native_schema_hash_array_read_verified"],
        "direct_bl_callers":report["direct_bl_callers_total"],
        "raw_function_pointer_cells":report["raw_function_pointer_cells_total"],
        "species_id_bindings_verified":0
    },ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
