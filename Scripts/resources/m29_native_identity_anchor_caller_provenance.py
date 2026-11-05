#!/usr/bin/env python3
"""M29: classify three ORIGINAL 2.0.1 Pokemon-related string consumers and
recover exact static KIDS class / BSS object accesses.

This is a deliberately narrower alternative to broad string or ARM64 "31"
searches. Three rodata strings appear in control paths involving:
- RegisterPokemonNum: counter/loop > 0x3e8 and calls a general text writer.
- pokemon_dex_id: selected x21 value and three bounded record u16s with
  explicit bitset checks at x22+4/+6/+8 (NOT source OID).
- m_mainPokemonList: x19+0x26 flags and x3 string passed to helper 0x5a71e0.

A rodata reference or a matching property hash never proves game species ID.
The last stage still needs a same-instance runtime KIDS source-OID lookup.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN, SHA_MAIN, arm64_window, branch_target, decode_adrp
)

OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M29")
ANCHORS={
    "RegisterPokemonNum":{
        "site":0x1135B44,
        "literal":"RegisterPokemonNum",
        "expected_rodata":0x27F2200,
        "start":0x1135AD4,"stop":0x1135BE8,
        "helper_pc":0x1135B4C,"helper":0x27470E0,
        "role":"native_string_argument_with_counter_or_aggregator"}
    ,
    "pokemon_dex_id":{
        "site":0x1136AA4,
        "literal":"pokemon_dex_id",
        "expected_rodata":0x27B1722,
        "start":0x1136950,"stop":0x1136AE8,
        "helper_pc":0x1136AB0,"helper":0x27470E0,
        "role":"native_string_argument_with_three_bounded_u16_and_bitset_tests"}
    ,
    "m_mainPokemonList":{
        "site":0x5FD168,
        "literal":"m_mainPokemonList",
        "expected_rodata":0x27D2B35,
        "start":0x5FD068,"stop":0x5FD220,
        "helper_pc":0x5FD174,"helper":0x5A71E0,
        "role":"native_string_argument_under_object_flag_control"}
}
TYPEGLOBALS={
    "class_owner_ptr":0x349C2E0,
    "class_vtable_ptr":0x349C2E8,
    "type_initialization_support":0x349C2D8,
    "static_BSS_owner":0x367AD40,
}
EXTRA_METHODS={
    "native_kids_class_property_method":0xDD1B48,
    "native_kids_typehash_method":0xDD1C30,
    "native_object_property_serializer":0x113AF80,
    "general_string_key_helper":0x27470E0,
    "list_named_query_helper":0x5A71E0,
}
CHECK={
    "RegisterPokemonNum":{
        0x1135B14:("cmp w21, #0x3e8",),
        0x1135B3C:("sxtw x2, w8",),
        0x1135B48:("mov x0, x19",),
        0x1135B4C:("bl #0x27470e0",),
        0x1135BC4:("cmp w12, #0x1f3",),
    },
    "pokemon_dex_id":{
        0x1136980:("ldrh w8, [x22, #4]",),
        0x1136A14:("ldrh w8, [x22, #6]",),
        0x1136A60:("ldrh w8, [x22, #8]",),
        0x1136A68:("cmp w9, #0x1f3",),
        0x1136AAC:("mov x2, x21",),
        0x1136AB0:("bl #0x27470e0",),
    },
    "m_mainPokemonList":{
        0x5FD094:("ldrb w8, [x19, #0x26]",),
        0x5FD164:("adrp x3,",),
        0x5FD168:("add x3, x3, #0xb35",),
        0x5FD16C:("mov x1, x19",),
        0x5FD170:("mov x2, x21",),
        0x5FD174:("bl #0x5a71e0",),
    },
}

def word(buf,at):return struct.unpack_from("<I",buf,at)[0]

def span(parts,addr,n):
    for s in parts:
        off=addr-s["mem_offset"]
        if 0<=off and off+n<=len(s["data"]):
            return s["name"],s["data"][off:off+n]
    return "",None

def try_effective_address(p,base,offset,reg,lookahead=6):
    """Syntactic ADRP and later ADD/LDR address provenance, not liveness."""
    matches=[]
    for j in range(1,lookahead+1):
        o=offset+j*4
        if o+4>len(p):break
        w=word(p,o)
        if ((w&0xFF000000)==0x91000000 and ((w>>5)&31)==reg):
            sh=(w>>22)&3
            if sh<=1:
                imm=((w>>10)&4095)<<(12 if sh else 0)
                matches.append(("ADD_ADDR",imm,j))
        elif ((w&0xFFC00000)==0xF9400000 and ((w>>5)&31)==reg):
            matches.append(("LDR_X",((w>>10)&4095)*8,j))
        elif ((w&0xFFC00000)==0xB9400000 and ((w>>5)&31)==reg):
            matches.append(("LDR_W",((w>>10)&4095)*4,j))
    return matches

def global_refs(buf,base):
    wanted=set(TYPEGLOBALS.values())
    pages={x&~4095 for x in wanted}
    ref=[]
    for off in range(0,len(buf)-4,4):
        pc=base+off
        d=decode_adrp(word(buf,off),pc)
        if d is None or d[0] not in pages:continue
        page,reg=d
        for op,imm,apart in try_effective_address(buf,base,off,reg):
            at=page+imm
            if at not in wanted:continue
            ref.append({
                "adrp_pc":hex(pc),"access_pc":hex(pc+4*apart),
                "native_cell":hex(at),
                "global_role":[k for k,v in TYPEGLOBALS.items() if v==at],
                "access_opcode":op,
                "instruction_distance":apart,
                "adjacent_register_syntax_confirmed":apart==1,
                "register_liveness_if_far":"UNPROVEN",
                "original_game_entity_id_source_verified":False,
            })
    return ref

def main_run():
    binary=MAIN.read_bytes()
    if hashlib.sha256(binary).hexdigest()!=SHA_MAIN:
        raise ValueError("M29 original NSO SHA-256 mismatch")
    kind,parts=get_sections(binary)
    if kind!="NSO0":raise ValueError("Original NSO0 required")
    text=next(p for p in parts if p["name"]=="text")
    code,base=text["data"],text["mem_offset"]
    report={}
    for name,a in ANCHORS.items():
        section,lit=span(parts,a["expected_rodata"],len(a["literal"])+1)
        if section!="rodata" or lit!=a["literal"].encode()+b"\0":
            raise ValueError(f"Original rodata string bytes have changed: {name}")
        win=arm64_window(code,base,a["site"],a["site"]-a["start"],a["stop"]-a["site"])
        bypc={int(x["pc"],16):x for x in win}
        exact=[]
        for pc,frags in CHECK[name].items():
            asm=bypc.get(pc,{}).get("asm","")
            if not all(f in asm for f in frags):
                raise ValueError(f"Original AArch64 operand relation modified {name}/{pc:x}: {asm}")
            exact.append({"pc":hex(pc),"original_word":bypc[pc]["word"],"asm":asm})
        # Original branch immediate rather than relying solely on mnemonics:
        at=a["helper_pc"]
        actual=branch_target(at,word(code,at-base))
        if actual!=(a["helper"],"BL"):
            raise ValueError(f"Original {name} BL destination changed: {actual}")
        d=decode_adrp(word(code,a["site"]-base-4),a["site"]-4)
        if d is None:raise ValueError("Original xref ADRP absent")
        # Literal adjacent ADD => exact effective address; register checked.
        w=word(code,a["site"]-base)
        if (w&0xff000000)!=0x91000000 or (w>>5)&31!=d[1]:
            raise ValueError("Original xref ADRP+ADD register mismatch")
        va=d[0]+((w>>10)&4095)
        if va!=a["expected_rodata"]:
            raise ValueError(f"Original string pointer is not exact: {name}/{va:x}")
        direct=[]
        for x in win:
            pc=int(x["pc"],16)
            b=branch_target(pc,int(x["word"],16))
            if b:
                direct.append({"pc":hex(pc),"type":b[1],"target":hex(b[0])})
        report[name]={
            "original_string":name,
            "original_rodata_va":hex(a["expected_rodata"]),
            "original_ref_adrp_pc":hex(a["site"]-4),
            "original_ref_add_pc":hex(a["site"]),
            "original_helper_bl_pc":hex(a["helper_pc"]),
            "original_helper_target":hex(a["helper"]),
            "string_helper_direct_call_proven":True,
            "narrow_native_evidence_role":a["role"],
            "verified_critical_instructions":exact,
            "local_direct_branch_targets":direct,
            "original_local_code_window":win,
            "exact_game_species_number_field_semantics_proven":False,
            "KIDS_Source_OID_correlated_same_instance_proven":False,
        }

    refs=global_refs(code,base)
    # A direct call graph to a *virtual method body* is not generally
    # expected; zero direct BL callers does not negate runtime BLR use.
    targetset=set(EXTRA_METHODS.values())
    directs={k:{"target":hex(v),"BL_sites":[],"B_sites":[]} for k,v in EXTRA_METHODS.items()}
    for off in range(0,len(code)-4,4):
        pc=base+off
        b=branch_target(pc,word(code,off))
        if b and b[0] in targetset:
            for label,a in EXTRA_METHODS.items():
                if a==b[0]:
                    directs[label][b[1]+"_sites"].append(hex(pc))
    for label,d in directs.items():
        d["BL_count"]=len(d["BL_sites"])
        d["B_count"]=len(d["B_sites"])
        d["BL_sites"]=d["BL_sites"][:150]
        d["B_sites"]=d["B_sites"][:150]
        d["indirect_virtual_callers_exhausted"]=False
    summary={
        "game_version":"2.0.1",
        "original_exefs_main_sha256":SHA_MAIN,
        "verified_three_identity_or_list_rodata_anchors":len(report),
        "register_pokemon_num_is_associated_with_upto_1000_loop":True,
        "pokemon_dex_id_anchor_has_three_u16_field_reads":[4,6,8],
        "pokemon_dex_id_u16_checked_up_to_500_values":True,
        "main_pokemon_list_has_flag_byte_at_offset":"0x26",
        "register_pokemon_num_handler":"0x27470e0",
        "pokemon_dex_id_handler":"0x27470e0",
        "main_pokemon_list_handler":"0x5a71e0",
        "native_kids_class_global_refs_count":len(refs),
        "native_kids_class_adjacent_global_refs_count":sum(x["adjacent_register_syntax_confirmed"] for x in refs),
        "direct_original_kids_property_method_call_count":directs["native_kids_class_property_method"]["BL_count"],
        "direct_original_type_getter_call_count":directs["native_kids_typehash_method"]["BL_count"],
        "exact_native_game_species_field_proven":False,
        "same_instance_entity_id_to_kids_source_oid_proven":False,
        "native_villager_ID_to_icon_OID_verified":False,
        "native_species_ID_to_texture_OID_verified":False,
        "note":"RegisterPokemonNum is used beside global counter and loops; pokemon_dex_id is used as a rodata key with x21 and bounded u16/bitsets; m_mainPokemonList accompanies x19+0x26 flag byte and conditional general handler. All are CODE facts, not proof these are the sprite-selection consumers. Direct BL calls to virtual methods are insufficient to cover BLR.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m29_original_identity_anchor_context_and_KIDS_class_refs.json").write_text(
        json.dumps({"source_anchor_windows":report,
                    "native_KIDS_class_global_source_xrefs":refs,
                    "targeted_direct_branch_callees":directs},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m29_native_identity_consumer_triage_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert len(ANCHORS)==3
    assert ANCHORS["pokemon_dex_id"]["helper"]==ANCHORS["RegisterPokemonNum"]["helper"]
    assert ANCHORS["m_mainPokemonList"]["helper"]!=ANCHORS["pokemon_dex_id"]["helper"]
    assert len(TYPEGLOBALS)==4
    print("PASS three original string/call/record hypotheses and original class address invariants")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:main_run()

if __name__=="__main__":main()
