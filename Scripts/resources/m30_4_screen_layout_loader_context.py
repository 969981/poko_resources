#!/usr/bin/env python3
"""M30.4: source-qualified AArch64 windows for ScreenLayout texture loading.

This follows original string xrefs discovered in M30.3 and looks for local
direct call targets / indirect BLR. It DOES NOT assert the code performs a
Pokémon species-ID lookup. Output supports later debugger stop selection.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import Counter
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m20_native_species_item_targets import (
    MAIN,SHA_MAIN,arm64_window,branch_target,decode_adrp
)
OUT=Path("UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M30")
ANCHORS={
    "screen_layout_texture_pack_settings":(0xBAA51C,0x27B09B9,"ScreenLayoutTexturePackSettings"),
    "static_screen_layout_textures":(0xBA6A10,0x279B44D,"StaticScreenLayoutTextures"),
    "static_screen_layout_texinfo_file":(0xBA5798,0x27F102D,"StaticScreenLayoutTexInfoFile"),
    "screen_layout_object_name_hash":(0xD3762C,0x27D8352,"ScreenLayoutObjectNameHash"),
    "screen_layout_generic":(0xBA5BF8,0x27FE4F3,"ScreenLayout"),
}
def mapped(parts,va,n):
    for p in parts:
        off=va-p["mem_offset"]
        if 0<=off and off+n<=len(p["data"]):
            return p["name"],p["data"][off:off+n]
    return "",None
def word(text,base,pc):
    return struct.unpack_from("<I",text,pc-base)[0]
def run():
    raw=MAIN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SHA_MAIN:raise ValueError("Not pinned original ExeFS 2.0.1")
    kind,parts=get_sections(raw)
    if kind!="NSO0":raise ValueError("Expected original NSO")
    x=next(p for p in parts if p["name"]=="text")
    code,base=x["data"],x["mem_offset"]
    result=[]
    for name,(ref,original_va,label) in ANCHORS.items():
        sec,lit=mapped(parts,original_va,len(label)+1)
        if sec!="rodata" or bytes(lit)!=label.encode("ascii")+b"\x00":
            raise ValueError(f"Original rodata literal invalid {label}")
        d=decode_adrp(word(code,base,ref),ref)
        # M30.3 source-ref PC is the ADRP; ADD follows at +4.
        if d is None:raise ValueError(f"No actual ADRP at {ref:#x}")
        nxt=word(code,base,ref+4)
        if (nxt&0xff000000)!=0x91000000 or ((nxt>>5)&31)!=d[1]:
            raise ValueError("Original address ADD does not use ADRP")
        shift=(nxt>>22)&3
        if shift>1:raise ValueError("Unexpected ADD shift")
        target=d[0]+(((nxt>>10)&4095)<<(12 if shift else 0))
        if target!=original_va:
            raise ValueError(f"Original {name} address differs: {target:#x}")
        win=arm64_window(code,base,ref,0x60,0xBC)
        direct=[]
        blr=[]
        for row in win:
            pc=int(row["pc"],16)
            w=int(row["word"],16)
            b=branch_target(pc,w)
            if b:
                direct.append({"site":hex(pc),"kind":b[1],"target":hex(b[0])})
            if row["asm"].split(" ",1)[0] in ("blr","blraa","blrab"):
                blr.append({"pc":hex(pc),"original_word":row["word"],"asm":row["asm"]})
        # Collect only distinct local direct BL targets; metadata/formatting
        # calls can be unrelated, so they remain candidates.
        first_bl=[]
        for item in direct:
            if item["kind"]!="BL":continue
            dest=int(item["target"],16)
            if not base<=dest<base+len(code):continue
            if any(x["callee_va"]==item["target"] for x in first_bl):continue
            first_bl.append({"callee_va":item["target"],"callsite":item["site"],
                "callee_first_20_bytes":arm64_window(code,base,dest,0,0x14)})
            if len(first_bl)>=10:break
        result.append({
            "name":name,
            "original_label":label,
            "original_rodata_address":hex(original_va),
            "original_string_xref_adrp":hex(ref),
            "original_string_xref_add":hex(ref+4),
            "verified_exact_ADRP_ADD_target":True,
            "local_direct_branch_sites":direct,
            "local_indirect_branch_sites":blr,
            "direct_BL_callee_first_instructions":first_bl,
            "original_reference_code_window":win,
            "screen_layout_loader_semantics_proven":False,
            "game_ID_to_icon_Source_OID_proven":False,
        })
    summary={
        "version":"2.0.1","original_main_sha256":SHA_MAIN,
        "original_screen_layout_texture_rodata_anchor_count":len(result),
        "verified_exact_adrp_add_string_addresses":len(result),
        "local_direct_BL_sites":sum(sum(x["kind"]=="BL" for x in row["local_direct_branch_sites"]) for row in result),
        "local_indirect_BLR_sites":sum(len(row["local_indirect_branch_sites"]) for row in result),
        "screen_layout_texture_loader_consumers_confirmed":False,
        "native_KIDS_icon_source_lookup_path_confirmed":False,
        "native_species_form_ID_binding_confirmed":False,
        "warning":"The native string references prove specific original ScreenLayout label sites and local code targets, not that the functions load Pokémon icons or join game IDs to Source OIDs.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"m30_4_screen_layout_texture_consumer_windows.json").write_text(
        json.dumps({"summary":summary,"code_regions":result},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT/"m30_4_screen_layout_consumer_triage_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:
        assert len(ANCHORS)==5
        print("PASS five original ScreenLayout source string targets")
    else:run()
