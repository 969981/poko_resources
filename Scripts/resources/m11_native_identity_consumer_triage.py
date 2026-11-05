#!/usr/bin/env python3
"""M11 Pokopia 2.0.1: native ARM64 caller evidence for sprite and item kinds.

Only original ExeFS NSO0 and native item records are used. The result ranks
testable field-consumer candidates, but NEVER asserts that a matching +0x26
load has an Item* base, nor that a 'pokemon_dex_id' string names a G1T.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from .trace_native_species_item_callers import get_sections

MAIN=Path("2.0.1/exefs/main")
ITEM=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
XREF=Path("UnPack/2.0.1/Resources/Pokemon/NativeCallers/main_string_xrefs.json")
OUT=Path("UnPack/2.0.1/Resources/Pokemon/NativeCallers/M11")
MAIN_SHA="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
ITEM_SHA="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
INTERESTING=("pokemon_dex_id","m_mainPokemonList","m_craftMainHelpPokemonKind",
             "m_craftRecipeId","m_craftHelpTable","m_PokemonSkill","m_pokemonDexHistory")
LIMIT=64

def words(code):
    return memoryview(code).cast("I")

def load_at(word):
    # [base, #immediate] uses scaled unsigned 12-bit offsets.
    load_ops=((0x39400000,"ldrb",1),(0x79400000,"ldrh",2),
              (0xB9400000,"ldr_w",4),(0xF9400000,"ldr_x",8))
    for opcode,kind,scale in load_ops:
        if (word&0xffc00000)==opcode:
            return kind,((word>>10)&4095)*scale,(word>>5)&31,word&31
    return None

def imm_at(word):
    if (word&0xff800000) in (0x52800000,0xd2800000):
        return ((word>>5)&65535)<<(((word>>21)&3)*16)
    # ADD 32/64 base,#12 uses optional shift of 12.
    if (word&0x7f000000)==0x11000000:
        shift=(word>>22)&3
        if shift<=1:
            return ((word>>10)&4095)<<(12 if shift else 0)
    return None

def context(md,code,base,pc,before=80,after=152):
    i=pc-base
    if not 0<=i<len(code):return []
    start=max(0,(i-before)&~3)
    end=min(len(code),(i+after+3)&~3)
    return [{"rva":f"0x{x.address:x}","op":x.mnemonic,
             "args":x.op_str,"word":code[x.address-base:x.address-base+4].hex()}
            for x in md.disasm(code[start:end],base+start)]

def classify_load_candidates(code,base):
    raw=words(code)
    sites=[]
    for idx,word in enumerate(raw):
        d=load_at(word)
        if d is not None and d[0]=="ldrb" and d[1]==0x26:
            sites.append((idx,d[2]))
    candidates=[]
    for idx,reg in sites:
        pre=range(max(0,idx-128),min(len(raw),idx+64))
        related=[]
        magic=[]
        for n in pre:
            w=raw[n]
            candidate=load_at(w)
            if candidate is not None and candidate[2]==reg and n!=idx and candidate[1] in (0x22,0x26,0x2a,0x3a):
                related.append({"offset":candidate[1],"kind":candidate[0],
                                "rva":base+n*4,"distance":(n-idx)*4})
            v=imm_at(w)
            if v in (68,4600):
                magic.append({"constant":v,"rva":base+n*4,"distance":(n-idx)*4})
        # Ranked leads, not field proof: count references with same register
        # could come from entirely different objects or unrelated functions.
        name_0x22=any(x["offset"]==0x22 and x["kind"]=="ldrh" for x in related)
        other=any(x["offset"] in (0x2a,0x3a) for x in related)
        stride=any(x["constant"]==68 for x in magic)
        count=any(x["constant"]==4600 for x in magic)
        score=12*name_0x22+3*other+3*stride+5*count
        if score:
            candidates.append({"pc":base+idx*4,"base_register":f"x{reg}",
                 "candidate_score":score,"same_base_loads":related[:24],
                 "nearby_immediates":magic[:24],
                 "native_item_base_verified":False})
    candidates.sort(key=lambda x:(-x["candidate_score"],x["pc"]))
    return {"total_load_0x26":len(sites),"ranked_candidates":len(candidates),
            "top":candidates[:LIMIT]}

def report(main,table,xrefs):
    if hashlib.sha256(main).hexdigest()!=MAIN_SHA:
        raise ValueError("ExeFS main differs from pinned original")
    if hashlib.sha256(table).hexdigest()!=ITEM_SHA:
        raise ValueError("Item table differs from pinned original")
    if len(table)!=64+4600*68 or struct.unpack_from("<II",table)!=(4600,3):
        raise ValueError("Item table count/stride/header mismatch")
    fmt,sections=get_sections(main)
    if fmt!="NSO0":
        raise ValueError("Original game executable must be NSO0")
    code=next(p for p in sections if p["name"]=="text")
    base=code["mem_offset"]
    buf=code["data"]
    try:
        from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    except ImportError as e:
        raise RuntimeError("capstone>=5 required") from e
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    # Bound and source-checked: xrefs were generated from the same NSO original.
    if xrefs.get("original_main_sha256")!=MAIN_SHA:
        raise ValueError("xrefs from different original NSO")
    targets=[x for x in xrefs["arm64_string_xrefs"]
             if any(t.lower()==x["string"].lower() for t in INTERESTING)]
    sites=[]
    for x in targets:
        pc=x["address"]
        if pc<base or pc>=base+len(buf):raise ValueError("xref address outside .text")
        rva=x["target_va"]
        ro=next((p for p in sections if p["name"]=="rodata"),None)
        if ro is None or not ro["mem_offset"]<=rva<ro["mem_offset"]+ro["size"]:
            raise ValueError("xref target not in original rodata")
        pos=rva-ro["mem_offset"]
        if not ro["data"][pos:pos+len(x["string"])].decode("ascii","replace")==x["string"]:
            raise ValueError("xref literal differs from native rodata")
        sites.append({"string":x["string"],"rva":pc,"target_rodata_rva":rva,
                      "instruction_window":context(md,buf,base,pc,128,224),
                      "binds_native_sprite_hash":False,"source":"original_NSO0_rodata_and_ARM64"})
    scored=classify_load_candidates(buf,base)
    for x in scored["top"]:
        x["assembly_window"]=context(md,buf,base,x["pc"],84,132)
    return {
        "status":"NATIVE_ARM64_TRIAGE_NOT_PROVEN_ID_BINDING",
        "game_version":"2.0.1","main_sha256":MAIN_SHA,"item_table_sha256":ITEM_SHA,
        "nso_text_bytes":len(buf),"native_item_count":4600,
        "native_item_record_stride":68,
        "verified_item_name_index_offset":34,
        "unverified_item_group_candidate_offset":38,
        "specific_rodata_callsite_count":len(sites),
        "specific_rodata_callsites":sites,
        "item_candidate_loads":scored,
        "species_id_to_texture_verified_count":0,
        "material_type_enum_confirmed":False,
        "next_proof":"Recover origin of xN base on +0x26 consumers as original ID-983 array; identify original Pokémon species field and its TEXINFO/G1T load consumer.",
        "warning":"A same-register offset match and nearby constants are NOT dataflow proof; do not assign official material class/species ID from this heuristic."
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--item-table",type=Path,default=ITEM)
    p.add_argument("--xref",type=Path,default=XREF)
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    d=report(a.main.read_bytes(),a.item_table.read_bytes(),
             json.loads(a.xref.read_text(encoding="utf-8")))
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"m11_native_callsite_triage.json").write_text(
        json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    minimal={k:v for k,v in d.items() if k not in ("specific_rodata_callsites","item_candidate_loads")}
    minimal.update({"species_callsite_rvas":[{"string":x["string"],"rva":f"0x{x['rva']:x}"}
                     for x in d["specific_rodata_callsites"]],
                    "item_best_candidates":[{"rva":f"0x{x['pc']:x}",
                     "score":x["candidate_score"],"base":x["base_register"]}
                        for x in d["item_candidate_loads"]["top"][:15]]})
    (a.out/"m11_summary.json").write_text(
        json.dumps(minimal,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(minimal,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
