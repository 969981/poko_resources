#!/usr/bin/env python3
"""M24.1: native pokemon identity-field anchor triage; NOT image-ID binding.

Provenance: same pinned NSO, original rodata literals, original instruction xrefs.
Only targeted source code windows around identity-related strings, no blind
promotion of 'pokemon_dex_id' to a texture KIDSOBJDB property.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    SHA_MAIN, MAIN, arm64_window, branch_target, u32,
)

BASE=Path("UnPack/2.0.1/Resources")
M20=BASE/"Pokemon/NativeCallers/main_string_xrefs.json"
M24=BASE/"Villagers/Native_2.0.1/M24/m24_original_consumer_summary.json"
OUT=BASE/"Villagers/Native_2.0.1/M24"
WANTED=("pokemon_dex_id","pokemon_dex","RegisterPokemonNum","m_mainPokemonList",
        "m_pokemonDexHistory","m_pokemonDexReadHistory","m_pokemonHistory")
ANCHORS={"pokemon_dex_id","RegisterPokemonNum","m_mainPokemonList"}

def span(sections,va,n):
    for sec in sections:
        at=va-sec["mem_offset"]
        if 0<=at and at+n<=len(sec["data"]):
            return sec["name"],sec["data"][at:at+n]
    return None,None

def track_code(code,base,pc):
    """Only exact mapped ARM64 code & local immediate branches are validated."""
    for_addr=arm64_window(code,base,pc,0x70,0xa0)
    branches=[]
    for r in for_addr:
        word=int(r["word"],16)
        x=branch_target(int(r["pc"],16),word)
        if x:
            branches.append({"pc":r["pc"],"kind":x[1],"target":hex(x[0]),
                             "target_is_within_text":base<=x[0]<base+len(code)})
    return for_addr,branches

def main_audit():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:raise ValueError("NSO source changed")
    prior=json.loads(M20.read_text(encoding="utf-8"))
    if prior["original_main_sha256"]!=SHA_MAIN:
        raise ValueError("String xrefs came from another version")
    m24=json.loads(M24.read_text(encoding="utf-8"))
    if m24["registry_type_hash"]!="0x79991e79" or m24["native_villager_id_bindings_verified"]!=0:
        raise ValueError("M24 trace baseline not immutable")
    kind,secs=get_sections(raw)
    if kind!="NSO0": raise ValueError("Not mapped original NSO")
    text=next(s for s in secs if s["name"]=="text")
    buf,base=text["data"],text["mem_offset"]

    by_name={name:[] for name in WANTED}
    for r in prior["arm64_string_xrefs"]:
        name=r["string"]
        if name not in by_name:continue
        actual=span(secs,int(r["target_va"]),len(name)+1)
        if actual[0]!="rodata" or actual[1]!=name.encode("ascii")+b"\x00":
            raise ValueError("Native identity literal target bytes mismatched")
        pc=int(r["address"])
        if pc<base or pc+4>base+len(buf) or pc%4:
            raise ValueError("Native xref outside text")
        # Verify exact second instruction word from M11 pointer arithmetic.
        if u32(buf,pc-base)!=int(r.get("add_word","0"),16):
            raise ValueError("Native rodata ADRP+ADD words altered")
        win,bl=track_code(buf,base,pc)
        by_name[name].append({
            "string":name,
            "literal_rodata_rva":hex(int(r["target_va"])),
            "string_xref_rva":hex(pc),
            "original_instruction_word":r["add_word"],
            "kind":r["kind"],
            "local_direct_branch_targets":bl,
            "native_code_window":win,
            "game_id_field_semantics":"UNVERIFIED",
            "native_texture_oid_binding_verified":False,
        })
    if any(not by_name[x] for x in ANCHORS):
        raise ValueError("Expected original identity string anchors absent")
    summary={
        "version":"2.0.1",
        "original_main_sha256":SHA_MAIN,
        "original_text_rodata_literals_exact_verified":True,
        "identity_literal_xref_count":sum(len(v) for v in by_name.values()),
        "anchor_counts":{k:len(v) for k,v in by_name.items()},
        "primary_identity_anchors":[{"name":k,"sites":[x["string_xref_rva"] for x in by_name[k]]}
                                    for k in sorted(ANCHORS)],
        "scope":"SOURCE_BYTES_ORIGINAL_STRING_ADRP_ADD_AND_BOUNDED_CALLSITE_CONTEXT",
        "direct_species_to_native_texture_id_verified":False,
        "gameplay_consumer_to_source_oid_verified":False,
        "9_ambiguous_identity_resolved":0,
        "79_missing_native_portraits_resolved":0,
        "warning":"Native save/serialization strings prove only those literals have executable references. Their consumers have NOT been linked to KIDS texture OIDs.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m24_1_identity_anchors_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m24_1_identity_anchors_asm.json").write_text(
        json.dumps(by_name,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary

def selftest():
    assert len(ANCHORS)==3
    assert ANCHORS.issubset(set(WANTED))
    assert branch_target(0x1000,0x94000400)==(0x2000,"BL")
    print("PASS narrow original identity string and branch decoder test")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:selftest()
    else:main_audit()

if __name__=="__main__": main()
