#!/usr/bin/env python3
"""M30.3: focused original NSO scan for ScreenLayout / TexturePack vocabulary
and original 0xE88C8D60/0x34CBB458 field hash CONST producers.

This starts from *newly recovered ORIGINAL property names*, not guessed
Pokémon species ID or broad generic registrar callsites.

Grades:
- Original string at exact ROdata VA and data pointer cell: literal evidence.
- MOVZ/MOVK constructing a property hash in the same register: syntactic
  candidate only; intervening clobber and function semantics not proven.
- Original code string xrefs built by adjacent ADRP+ADD: address evidence only.
No claim that the actual runtime game ID was passed to a lookup.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import struct
from collections import Counter,defaultdict
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN,SHA_MAIN,arm64_window,decode_adrp
)

OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M30")
WORDS={0x2F610FEA:"ScreenLayoutTexturePackObjectNameHash",
       0xE88C8D60:"TexturePackKeyHashArray",
       0x34CBB458:"TexturePackObjectHashArray"}
NAMES=("TexturePack","ScreenLayout")
SAMPLE_LIMIT=90

def w32(b,off):return struct.unpack_from("<I",b,off)[0]

def literal_rows(rodata):
    data=rodata["data"];base=rodata["mem_offset"]
    hits=[]
    for m in re.finditer(rb"[\x20-\x7e]{4,160}\x00",data):
        raw=m.group(0)[:-1]
        if any(s.encode() in raw for s in NAMES):
            text=raw.decode("ascii")
            hits.append({"original_rodata_VA":hex(base+m.start()),
                         "literal":text,
                         "literal_length":len(raw),
                         "contains_TexturePack":"TexturePack" in text,
                         "contains_ScreenLayout":"ScreenLayout" in text,
                         "directly_KIDS_property_name":text in WORDS.values()})
    return hits

def mov_pair_candidates(code,base,targets):
    """Recognize MOVZ(#low), followed within 1..8 by same-reg MOVK(#upper).
    (No inter-instruction register liveness asserted.)"""
    lo={v&0xffff:v for v in targets}
    candidates=[]
    for off in range(0,len(code)-4,4):
        z=w32(code,off)
        # 32 or 64-bit MOVZ, HW=0
        if (z&0x7f800000)!=0x52800000 or ((z>>21)&3)!=0:
            continue
        initial=(z>>5)&0xffff
        if initial not in lo:continue
        r=z&31
        target=lo[initial]
        hi=target>>16
        for steps in range(1,9):
            nxt=off+steps*4
            if nxt+4>len(code):break
            word=w32(code,nxt)
            if ((word&0x7f800000)!=0x72800000 or
                ((word>>21)&3)!=1 or (word&31)!=r or ((word>>5)&0xffff)!=hi):
                continue
            candidates.append({"first_pc":hex(base+off),
                "second_pc":hex(base+nxt),"steps_apart":steps,
                "first_original_word":f"{z:08x}",
                "second_original_word":f"{word:08x}",
                "result_target_hash":f"{target:08x}",
                "original_property_label":WORDS[target],
                "same_register":f"w{r}",
                "runtime_property_consumer_verified":False,
                "original_register_liveness_proven":steps==1,
                "game_species_ID_mapping_verified":False})
    return candidates

def run():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:
        raise ValueError("Original NSO0 hash changed")
    kind,parts=get_sections(raw)
    if kind!="NSO0":raise ValueError("Original NSO mapping required")
    code=next(p for p in parts if p["name"]=="text")
    rodata=next(p for p in parts if p["name"]=="rodata")
    data=next(p for p in parts if p["name"]=="data")
    found=literal_rows(rodata)
    if not {"TexturePackKeyHashArray","TexturePackObjectHashArray",
            "ScreenLayoutTexturePackObjectNameHash"}.issubset({x["literal"] for x in found}):
        raise ValueError("Original M30.2 three property names not in source rodata")
    name_index={int(x["original_rodata_VA"],16):x for x in found}
    pointer_refs=defaultdict(list)
    for off in range(0,len(data["data"])-7,8):
        x=struct.unpack_from("<Q",data["data"],off)[0]
        if x in name_index:
            pointer_refs[x].append(hex(data["mem_offset"]+off))
    for row in found:
        row["initialized_data_pointer_cells"]=pointer_refs.get(int(row["original_rodata_VA"],16),[])
    # Exact adjacent instruction effective address; only for the first
    # few rodata labels and source pointers to limit false positives.
    by_page=defaultdict(set)
    for row in found:
        a=int(row["original_rodata_VA"],16)
        by_page[a&~4095].add(a)
    literal_xrefs=defaultdict(list)
    for off in range(0,len(code["data"])-7,4):
        pc=code["mem_offset"]+off
        d=decode_adrp(w32(code["data"],off),pc)
        if d is None or d[0] not in by_page:continue
        page,reg=d
        nxt=w32(code["data"],off+4)
        if nxt&0xff000000!=0x91000000 or (nxt>>5)&31!=reg:
            continue
        shift=(nxt>>22)&3
        if shift>1:continue
        imm=((nxt>>10)&4095)<<(12 if shift else 0)
        a=page+imm
        if a in by_page[page]:
            literal_xrefs[a].append({"adrp_pc":hex(pc),"add_pc":hex(pc+4),
                                    "source_word":f"{w32(code['data'],off):08x}",
                                    "add_word":f"{nxt:08x}",
                                    "proof_grade":"EXACT_ADJACENT_RODATA_ADDRESS_ONLY",
                                    "runtime_method_semantics_verified":False})
    for row in found:
        row["code_adrp_add_xrefs"]=literal_xrefs.get(int(row["original_rodata_VA"],16),[])
    mods=mov_pair_candidates(code["data"],code["mem_offset"],WORDS)
    for c in mods[:SAMPLE_LIMIT]:
        at=int(c["first_pc"],16)
        c["original_local_asm"]=arm64_window(code["data"],code["mem_offset"],at,0x18,0x30)
    raw_consts=defaultdict(list)
    for p in parts:
        if p["name"] not in ("rodata","data"):continue
        b=p["data"]
        for off in range(0,len(b)-3,4):
            v=w32(b,off)
            if v in WORDS:
                raw_consts[v].append({"section":p["name"],"pc_or_va":hex(p["mem_offset"]+off)})
    summary={
        "version":"2.0.1","original_main_sha256":SHA_MAIN,
        "original_rodata_string_hits_with_ScreenLayout_or_TexturePack":len(found),
        "original_strings_containing_ScreenLayout":sum(x["contains_ScreenLayout"] for x in found),
        "original_strings_containing_TexturePack":sum(x["contains_TexturePack"] for x in found),
        "property_names_exact":list(WORDS.values()),
        "literal_string_initialized_data_pointer_cells":sum(len(v) for v in pointer_refs.values()),
        "original_literal_adrp_add_code_refs":sum(len(v) for v in literal_xrefs.values()),
        "candidate_hash_producers_MOVZ_MOVK":len(mods),
        "candidate_hash_producer_counts":dict(Counter(x["original_property_label"] for x in mods)),
        "original_little_endian_raw_hash_cells_by_field":{
            WORDS[k]:v[:40] for k,v in raw_consts.items()
        },
        "native_3543_texture_pack_query_consumer_verified":False,
        "game_species_form_to_texture_pack_key_verified":False,
        "runtime_villager_ID_to_Source_OID_proven":False,
        "warning":"Literal field labels and source constant construction are not KIDS 3543-array consumers. Direct data pointers into rodata are strings, not native code callbacks.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m30_3_original_texture_pack_vocabulary_xrefs.json").write_text(
        json.dumps({"summary":summary,"original_texture_pack_literals":found,
                    "native_movz_movk_property_hash_candidates":mods[:SAMPLE_LIMIT]},
                   ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m30_3_texture_pack_consumer_triage_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert len(WORDS)==3 and len(NAMES)==2
    assert all(isinstance(x,int) for x in WORDS)
    print("PASS original three TexturePack property names and bounded byte patterns")

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:run()
