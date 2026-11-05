#!/usr/bin/env python3
"""Static-only investigation of original Switch2 ExeFS main.

Recovers NSO0 text/rodata with strict LZ4 bounds, surveys real icon_poke_
strings and searches ARM64 ADRP+ADD references.  Separately lists ldrb #0x26
instructions for later manual tracing of the candidate item type byte.

An address match is not itself species identity or material enum proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from collections import deque
from pathlib import Path

MAX_SEGMENT=256*1024*1024
TEXT_HINTS=(b"icon_poke", b"item_type", b"itemkind", b"material", b"craft",b"pokemon")
printable=re.compile(rb"[\x20-\x7e]{5,400}(?:\x00|$)")


def u32(b,p):
    if p<0 or p+4>len(b):
        raise ValueError(f"NSO field missing at {p:#x}")
    return struct.unpack_from("<I",b,p)[0]


def get_sections(blob):
    if blob[:4]==b"NSO0":
        flags=u32(blob,0x0c)
        result=[]
        for i,name in enumerate(("text","rodata","data")):
            pos=0x10+i*0x10
            fileoff=u32(blob,pos)
            memoff=u32(blob,pos+4)
            unpacked=u32(blob,pos+8)
            packed=u32(blob,0x60+4*i)
            compressed=bool(flags & (1<<i))
            n=packed if compressed else unpacked
            if not 0<=n<=MAX_SEGMENT or not 0<=unpacked<=MAX_SEGMENT or fileoff+n>len(blob):
                raise ValueError(f"invalid NSO0 {name} section bounds")
            buf=blob[fileoff:fileoff+n]
            if compressed:
                try:
                    import lz4.block
                except ImportError as ex:
                    raise RuntimeError("NSO compressed sections need pip install lz4") from ex
                buf=lz4.block.decompress(buf,uncompressed_size=unpacked)
            if len(buf)!=unpacked:
                raise ValueError(f"{name} decompressed size mismatch")
            result.append({"name":name,"mem_offset":memoff,
                "file_offset":fileoff,"compressed":compressed,
                "size":len(buf),"data":buf})
        return "NSO0",result
    if blob[:4]==b"\x7fELF":
        # Avoid pretending an ELF file has linear 1:1 section virtual offsets.
        return "ELF_UNMAPPED",[{"name":"file_image",
            "mem_offset":0,"file_offset":0,"compressed":False,
            "size":len(blob),"data":blob}]
    return f"UNKNOWN_{blob[:8].hex()}",[{"name":"raw_blob","mem_offset":0,
        "file_offset":0,"compressed":False,"size":len(blob),"data":blob}]


def scan_strings(parts):
    found=[]
    for part in parts:
        if part["name"]=="text":
            continue
        blob=part["data"]
        for match in printable.finditer(blob):
            raw=match.group(0).rstrip(b"\0")
            low=raw.lower()
            if not any(token in low for token in TEXT_HINTS):
                continue
            found.append({"section":part["name"],"raw_file_offset":part["file_offset"]+match.start(),
                "virtual_offset":part["mem_offset"]+match.start(),
                "text":raw[:220].decode("ascii","replace"),
                "target_group":"POKEMON_ICON" if b"icon_poke" in low
                    else ("MATERIAL_CRAFT_REFERENCE" if any(w in low for w in (b"material",b"craft",b"item_type",b"itemkind"))
                          else "OTHER_POKEMON_TEXT")})
    return found


def arm64_scan(text_segment, string_targets, max_type_loads=300):
    """Bounded raw ARM64 instruction scan; no 41-MB Capstone detail objects.

    ADRP + ADD immediates can be verified via fixed AArch64 instruction masks.
    This enumerates static candidates, not caller dataflow or proven identity.
    """
    blob=text_segment["data"]
    base=text_segment["mem_offset"]
    targets={t["virtual_offset"]:t for t in string_targets}
    pages={addr>>12 for addr in targets}
    refs=[]
    loads=[]
    aligned=len(blob)&~3
    seen=0
    for off in range(0,aligned,4):
        word=struct.unpack_from("<I",blob,off)[0]
        pc=base+off
        seen+=1
        # ADRP Rd, page: immlo bits[30:29], immhi bits[23:5].
        if pages and (word & 0x9F000000)==0x90000000:
            immlo=(word>>29)&3
            immhi=(word>>5)&0x7FFFF
            signed=(immhi<<2)|immlo
            if signed&(1<<20): signed-=1<<21
            page=(pc&~0xFFF)+(signed<<12)
            if (page>>12) in pages:
                reg=word&31
                for stride in (4,8,12,16,20):
                    if off+stride+4>aligned: break
                    nextword=struct.unpack_from("<I",blob,off+stride)[0]
                    # ADD Xd, Xn, #imm12[, LSL #12]
                    if (nextword&0xFF000000)!=0x91000000:
                        continue
                    rn=(nextword>>5)&31
                    if rn!=reg: continue
                    shift=(nextword>>22)&3
                    if shift not in (0,1): continue
                    imm=(nextword>>10)&0xFFF
                    va=page+(imm<<(12 if shift==1 else 0))
                    if va in targets:
                        refs.append({
                            "address":pc+stride,"adrp_address":pc,
                            "kind":"ADRP_ADD_RAW_AARCH64",
                            "target_va":va,"string":targets[va]["text"],
                            "adrp_word":f"{word:08x}",
                            "add_word":f"{nextword:08x}"})
        # ADR Rd, address (without page).
        elif pages and (word & 0x9F000000)==0x10000000:
            val=(((word>>5)&0x7FFFF)<<2)|((word>>29)&3)
            if val&(1<<20):val-=1<<21
            target=pc+val
            if target in targets:
                refs.append({"address":pc,"kind":"ADR_RAW_AARCH64",
                             "target_va":target,"string":targets[target]["text"],
                             "instruction_word":f"{word:08x}"})
        if len(loads)<max_type_loads:
            # LDRB Wt, [Xn, #imm12], unscaled instruction kind may differ.
            is_byte=(word&0xFFC00000)==0x39400000 and ((word>>10)&0xFFF)==0x26
            # LDRH Wt,[Xn,#imm12*2]; byte displacement 0x26 = 0x13*2.
            is_half=(word&0xFFC00000)==0x79400000 and ((word>>10)&0xFFF)==0x13
            if is_byte or is_half:
                nearby=[
                    f"{struct.unpack_from('<I',blob,x)[0]:08x}"
                    for x in range(max(0,off-20),off,4)
                ]
                loads.append({"address":pc,"kind":"LDRB_0X26" if is_byte else "LDRH_0X26",
                              "instruction_word":f"{word:08x}",
                              "prior_instruction_words":nearby,
                              "needs_base_register_dataflow":True})
    return refs,loads,{
        "inspected_instructions":seen,"text_bytes":len(blob),
        "byte_coverage":aligned,"algorithm":"strict raw AArch64 word/ADRP/ADD/LDRB masks"
    }


def analyze(blob, max_xref=100):
    kind,parts=get_sections(blob)
    matches=scan_strings(parts)
    icon=[x for x in matches if x["target_group"]=="POKEMON_ICON"]
    others=[x for x in matches if x["target_group"]!="POKEMON_ICON"]
    refs,loads,coverage=[],[],{}
    code=next((p for p in parts if p["name"]=="text"),None)
    # NSO contains no literal icon_poke_ in many optimized builds. Trace
    # native adjacent PokemonKind/crafting terms too, but do NOT treat these
    # as verified sprite or material enum consumers.
    anchors=icon+[
        x for x in others if re.search(r"pokemon|craft|recipe|itemkind|item_type",
                                        x["text"],re.IGNORECASE)
    ]
    if code:
        refs,loads,coverage=arm64_scan(code,anchors)
    return {
        "status":"STATIC_FORENSICS_ONLY__NATIVE_ID_NOT_PROVEN",
        "original_main_sha256":hashlib.sha256(blob).hexdigest(),
        "format":kind,
        "header_bytes_hex":blob[:32].hex(),
        "segments":[{k:v for k,v in p.items() if k!="data"} for p in parts],
        "pokemon_literal_count":len(icon),
        "pokemon_literals":icon[:max_xref],
        "other_related_string_count":len(others),
        "other_related_strings":others[:max_xref],
        "arm64_survey_coverage":coverage,
        "tracked_literal_anchors":len(anchors),
        "arm64_string_xrefs_count":len(refs),
        "arm64_string_xrefs":refs[:max_xref],
        "ldrb_struct_offset_0x26_samples":loads[:max_xref],
        "species_id_confirmed":0,
        "material_enum_confirmed":False,
        "warning":"String or ldrb offsets in ExeFS are candidate anchors only. Confirm struct base, caller, ID input dataflow and runtime bindings before assigning any species/material type."
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=Path("2.0.1/exefs/main"))
    p.add_argument("--output",type=Path,default=Path("UnPack/2.0.1/Resources/Pokemon/NativeCallers/main_string_xrefs.json"))
    args=p.parse_args()
    report=analyze(args.main.read_bytes())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("status","format","segments",
        "pokemon_literal_count","other_related_string_count",
        "arm64_string_xrefs_count","species_id_confirmed")},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
