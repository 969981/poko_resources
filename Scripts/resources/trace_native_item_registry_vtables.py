#!/usr/bin/env python3
"""M14: Inspect NSO MOD0 dynamic relocations and executable virtual tables.

Goal: constrain the +0x30 vtable function reached through object registry 0xC7.
This stage deliberately does NOT claim a specific class-vtable binding until
construction and registry insertion are proved.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import defaultdict,Counter
from pathlib import Path
from Scripts.resources.trace_native_species_item_callers import get_sections

EXPECTED_MAIN="8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
EXPECTED_ITEM="2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
MAIN=Path("2.0.1/exefs/main")
ITEM=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M14")
# Nintendo Switch NSO uses AArch64 Elf relocation values.
R_AARCH64_RELATIVE=1027
DT_NULL=0
DT_RELA=7
DT_RELASZ=8
DT_RELAENT=9
DT_RELACOUNT=0x6ffffff9
KNOWN_CALLERS=[0xE5AA38,0x10289E0,0xABBB48,0xABBBB8]
KNOWN_REGISTRY=0xC7
MAX_RELA=5_000_000

def u32(data,off):
    if 0<=off<=len(data)-4:return struct.unpack_from("<I",data,off)[0]
    raise ValueError("out-of-bounds u32")

def u64(data,off):
    if 0<=off<=len(data)-8:return struct.unpack_from("<Q",data,off)[0]
    raise ValueError("out-of-bounds u64")

def s64(data,off):
    if 0<=off<=len(data)-8:return struct.unpack_from("<q",data,off)[0]
    raise ValueError("out-of-bounds s64")

def locate(parts,addr,size):
    for p in parts:
        start=p["mem_offset"]; end=start+len(p["data"])
        if start<=addr and addr+size<=end:
            return p,p["data"],addr-start
    return None,None,None

def mod0_probe(parts):
    """NSO text[4] is often an image/module VA into rodata, not text-relative."""
    text=next(p for p in parts if p["name"]=="text")
    b=text["data"]
    value=u32(b,4)
    info={"text_first_64_hex":b[:64].hex(),
          "word_at_text_plus_4":hex(value)}
    bases=[("image_va",value),("text_relative",text["mem_offset"]+value)]
    for mode,va in bases:
        p,buf,idx=locate(parts,va,64)
        if p is None or buf[idx:idx+4]!=b"MOD0":
            continue
        info.update(mod0_found=True,mod0_offset=hex(va),
                    mod0_section=p["name"],mod0_pointer_mode=mode,
                    mod0_header_64_hex=buf[idx:idx+64].hex())
        rel=struct.unpack_from("<i",buf,idx+4)[0]
        info["dynamic_relative"]=rel
        return info,va,rel
    info.update(mod0_found=False,
                candidate_virtual_addresses=[{"mode":k,"va":hex(v)} for k,v in bases])
    return info,None,None


def dynamic_probe(parts,modbase,reldyn):
    if modbase is None:return [],{"status":"MOD0_NOT_FOUND"}
    addr=modbase+reldyn
    entries=[]
    for i in range(1024):
        p,buf,idx=locate(parts,addr+i*16,16)
        if p is None:break
        tag=s64(buf,idx)
        value=u64(buf,idx+8)
        entries.append({"tag":tag,"value":value})
        if tag==DT_NULL:break
    tags=defaultdict(list)
    for e in entries:tags[e["tag"]].append(e["value"])
    return entries,{"status":"DYNAMIC_PARSED" if entries and entries[-1]["tag"]==DT_NULL else "DYNAMIC_PARTIAL",
                    "dynamic_va":hex(addr),"entry_count":len(entries),
                    "selected_tags":{str(k):[hex(x) for x in v[:5]] for k,v in tags.items() if k in
                                       (DT_RELA,DT_RELASZ,DT_RELAENT,DT_RELACOUNT)}}

def relocation_probe(parts,modbase,dynamic):
    tags={}
    for e in dynamic:tags.setdefault(e["tag"],e["value"])
    report={"status":"NO_RELA_TAG","counts":{},"candidate_base_modes":{}}
    if not all(k in tags for k in (DT_RELA,DT_RELASZ)):return {},report
    size=tags[DT_RELASZ]; stride=tags.get(DT_RELAENT,24)
    if stride!=24 or size%24 or size//24>MAX_RELA:
        return {},{"status":"INVALID_RELA_TABLE_SIZE","rela_bytes":size,"stride":stride}
    # Depending on linker, dynamic d_ptr may be module VA or MOD0-relative.
    target=tags[DT_RELA]
    attempts=[("module_va",target),("mod0_relative",modbase+target)]
    good=[]
    for mode,addr in attempts:
        p,buf,idx=locate(parts,addr,size)
        if p is not None:good.append((mode,addr,p,buf,idx))
    if not good:
        return {},{"status":"RELA_POINTER_UNMAPPED","rela_pointer":hex(target),
                   "rela_size":size,"tried":[[k,hex(v)] for k,v in attempts]}
    # parse enough to determine quality, then retain RELATIVE where addend
    # refers to an executable address and slot lies in the mapped NSO image.
    best=None
    for mode,addr,p,buf,idx in good:
        hits={};counts=Counter();unmapped=0
        for i in range(size//24):
            offset,info,addend=struct.unpack_from("<QQq",buf,idx+i*24)
            typ=info&0xffffffff
            counts[typ]+=1
            if typ==R_AARCH64_RELATIVE:
                cell,_,_=locate(parts,offset,8)
                target_seg,_,_=locate(parts,addend,4)
                if cell is not None and target_seg is not None and target_seg["name"]=="text":
                    hits[offset]=addend
                elif cell is None:unmapped+=1
        quality=len(hits)
        if best is None or quality>best[0]:
            best=(quality,hits,counts,mode,addr,unmapped)
    _,hits,counts,mode,addr,unmapped=best
    return hits,{"status":"RELA_PARSED","mode":mode,"rela_va":hex(addr),
                 "rela_count":sum(counts.values()),"rela_types":dict(counts),
                 "relative_text_pointer_count":len(hits),"unmapped_relocation_cells":unmapped}

def raw_pointers(parts,text_end):
    hits={}
    for p in parts:
        if p["name"] not in ("data","rodata"):continue
        b=p["data"]
        for o in range(0,len(b)-7,8):
            v=struct.unpack_from("<Q",b,o)[0]
            if v%4==0 and 0x1000<=v<text_end:
                hits[p["mem_offset"]+o]=v
    return hits

def functions(parts,pointers,limit=120):
    text=next(p for p in parts if p["name"]=="text")
    end=text["mem_offset"]+len(text["data"])
    # Potential 0x30 vtable slot at slot (six x8 entries after table base).
    candidates=[]
    for slot,func in pointers.items():
        base=slot-0x30
        if base<0:continue
        # Only consider the first pointer in each dense run. Sliding the
        # "vtable base" by 8 creates hundreds of thousands of false vtables.
        if base-8 in pointers:continue
        hits={hex(i):hex(pointers[base+i]) for i in range(0,0x60,8) if base+i in pointers}
        prior=sum(1 for i in range(0,0x30,8) if base+i in pointers)
        after=sum(1 for i in (0x30,0x38,0x40,0x48,0x50,0x58) if base+i in pointers)
        if prior<3 or after<2:continue
        score=prior*2+after
        candidates.append((score,base,func,hits))
    candidates.sort(key=lambda x:(-x[0],x[1]))
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    out=[]
    selected=set()
    for score,base,func,slots in candidates:
        if base in selected:continue
        selected.add(base)
        p,buf,off=locate(parts,func,min(0xc0,end-func))
        if p is None:continue
        asm=[{"pc":hex(i.address),"asm":i.mnemonic+" "+i.op_str}
             for i in md.disasm(buf[off:off+0xa0],func)]
        markers=[]
        for e in asm:
            if any(t in e["asm"] for t in ("#0x44","#0x11f8","#0x11f6","#0x26","#0x3a","#0xc7")):
                markers.append(e)
        out.append({"vtable_base":hex(base),"slot_va":hex(base+0x30),
                    "method_va":hex(func),"score_pointer_density":score,
                    "surrounding_slots":slots,"method_first_instructions":asm,
                    "interesting_immediates":markers,"status":"VTABLE_CANDIDATE_CLASS_UNBOUND"})
        if len(out)>=limit:break
    return out,len(candidates)

def analyze(main,item):
    sha1=hashlib.sha256(main).hexdigest();sha2=hashlib.sha256(item).hexdigest()
    if sha1!=EXPECTED_MAIN or sha2!=EXPECTED_ITEM:
        raise ValueError(f"original source SHA mismatch: {sha1}/{sha2}")
    if len(item)!=64+4600*68 or struct.unpack_from("<II",item,0)!=(4600,3):
        raise ValueError("item table source header/record size mismatch")
    kind,parts=get_sections(main)
    if kind!="NSO0":raise ValueError("not original NSO0")
    info,modbase,dynamic_offset=mod0_probe(parts)
    dynamic,modreport=dynamic_probe(parts,modbase,dynamic_offset)
    rel,relreport=relocation_probe(parts,modbase,dynamic)
    text=next(p for p in parts if p["name"]=="text")
    raw=raw_pointers(parts,text["mem_offset"]+len(text["data"]))
    # RELATIVE addend entries supersede raw bytes at the same slot.
    merged={**raw,**rel}
    entries,total=functions(parts,merged)
    return {"status":"VTABLE_RECOVERY_CANDIDATES__CLASS_AND_LOADER_UNRESOLVED",
            "sources":{"main_sha256":sha1,"item_sha256":sha2},
            "registry_index":hex(KNOWN_REGISTRY),
            "call_sites":[hex(x) for x in KNOWN_CALLERS],
            "virtual_method_offset":"0x30",
            "mod0":info,"dynamic":modreport,"relocations":relreport,
            "raw_text_pointer_cells":len(raw),"merged_text_pointer_cells":len(merged),
            "vtable_dense_candidate_count":total,
            "vtable_candidates":entries,
            "registry_to_concrete_vtable_confirmed":False,
            "virtual_method_to_original_item_record_confirmed":False,
            "return_object_plus8_to_00983_68_stride_confirmed":False,
            "warnings":[
                "Candidate vtables reconstructed from nearby executable pointers and RELA relocation addends only.",
                "No direct proof which vtable belongs to registry element 0xC7.",
                "C++ vtable may be in GOT/RELR, or have negative slots, linker optimization, or relative pointers.",
                "Method address is not the loader until constructor -> registry -> lookup result -> table allocation is traced."
            ]}

def selftest():
    sample=bytearray(0x300)
    # Fake text MOD0 at +0x40, dyn offset 0x20 (relative to MOD0).
    struct.pack_into("<I",sample,4,0x40)
    sample[0x40:0x44]=b"MOD0"
    struct.pack_into("<I",sample,0x44,0x20)
    struct.pack_into("<QQ",sample,0x60,DT_RELA,0xC0)
    struct.pack_into("<QQ",sample,0x70,DT_RELASZ,24)
    struct.pack_into("<QQ",sample,0x80,DT_RELAENT,24)
    struct.pack_into("<QQ",sample,0x90,DT_NULL,0)
    # relocation slot 0x400 -> executable 0x120
    struct.pack_into("<QQq",sample,0xC0,0x400,R_AARCH64_RELATIVE,0x120)
    # Test image-VA MOD0 pointer into a distinct rodata mapping.
    image=bytearray(0x300)
    struct.pack_into("<I",image,4,0x440)
    rodata=bytearray(0x400)
    rodata[0x40:0x44]=b"MOD0"
    struct.pack_into("<I",rodata,0x44,0x20)
    struct.pack_into("<QQ",rodata,0x60,DT_RELA,0x4c0)
    struct.pack_into("<QQ",rodata,0x70,DT_RELASZ,24)
    struct.pack_into("<QQ",rodata,0x80,DT_RELAENT,24)
    struct.pack_into("<QQ",rodata,0x90,DT_NULL,0)
    struct.pack_into("<QQq",rodata,0xC0,0x800,R_AARCH64_RELATIVE,0x120)
    image_parts=[{"name":"text","mem_offset":0,"data":bytes(image)},
                 {"name":"rodata","mem_offset":0x400,"data":bytes(rodata)},
                 {"name":"data","mem_offset":0x800,"data":b"\x00"*0x100}]
    found,newbase,newrel=mod0_probe(image_parts)
    assert found["mod0_found"] and found["mod0_pointer_mode"]=="image_va" and newbase==0x440
    newdyn,newdiag=dynamic_probe(image_parts,newbase,newrel)
    newptrs,newdiag2=relocation_probe(image_parts,newbase,newdyn)
    assert newptrs=={0x800:0x120},newdiag2

    parts=[{"name":"text","mem_offset":0,"data":bytes(sample)},
           {"name":"rodata","mem_offset":0x400,"data":b"\x00"*0x100}]
    info,base,off=mod0_probe(parts)
    assert info["mod0_found"] and base==0x40 and off==0x20
    dyn,dinfo=dynamic_probe(parts,base,off)
    assert dinfo["status"]=="DYNAMIC_PARSED"
    pointers,rinfo=relocation_probe(parts,base,dyn)
    assert pointers=={0x400:0x120},rinfo
    assert rinfo["relative_text_pointer_count"]==1
    try:
        analyze(b"forged",b"forged")
        raise AssertionError("invalid original input accepted")
    except ValueError:pass
    print("PASS: MOD0, dynamic RELA, mapped AArch64 relative text pointers, forged-source reject")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,default=MAIN)
    p.add_argument("--item",type=Path,default=ITEM)
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:selftest();return
    result=analyze(args.main.read_bytes(),args.item.read_bytes())
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/"registry_vtable_candidates.json").write_text(
        json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    summary={k:result[k] for k in ("status","sources","registry_index","call_sites","virtual_method_offset",
        "mod0","dynamic","relocations","raw_text_pointer_cells",
        "merged_text_pointer_cells","vtable_dense_candidate_count",
        "registry_to_concrete_vtable_confirmed",
        "virtual_method_to_original_item_record_confirmed",
        "return_object_plus8_to_00983_68_stride_confirmed")}
    summary["candidate_methods"]=[{k:v[k] for k in ("vtable_base","method_va","score_pointer_density","interesting_immediates")}
                                  for v in result["vtable_candidates"][:30]]
    (args.out/"registry_vtable_summary.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
