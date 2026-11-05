#!/usr/bin/env python3
"""M11.3: audit 983 -> BL -> BL -> native global pointer store. Not item proof."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
try:
    from .trace_native_item_provenance import MAIN_SHA,ITEM_SHA,get_sections,windows,movz_immediate
except ImportError:
    from trace_native_item_provenance import MAIN_SHA,ITEM_SHA,get_sections,windows,movz_immediate

CALLERS=(0x14fd9b0,0x14fdb1c)
FIRST,SECOND=0x1445e30,0x14718f0
PAGE,DISP=0x36d5000,0x4c8
OUT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M11")

def readword(code,base,pc):
    off=pc-base
    if off<0 or off%4 or off+4>len(code):raise ValueError("WORD_OUT_OF_BOUNDS")
    return struct.unpack_from("<I",code,off)[0]

def adrp_target(w,pc):
    if (w&0x9f000000)!=0x90000000:return None
    imm=(((w>>5)&0x7ffff)<<2)|((w>>29)&3)
    if imm&(1<<20):imm-=1<<21
    return (pc&~0xfff)+(imm<<12)

def bl_target(w,pc):
    if (w&0xfc000000)!=0x94000000:return None
    imm=w&0x3ffffff
    if imm&(1<<25):imm-=1<<26
    return pc+(imm<<2)

def mem_x(w,load):
    if (w&0xffc00000)!=(0xf9400000 if load else 0xf9000000):
        return None
    return ((w>>5)&31,w&31,((w>>10)&0xfff)*8)

def chain(code,base,pc):
    a,b,c,d,e=[readword(code,base,pc+4*i) for i in range(5)]
    if not (movz_immediate(a)==983 and (a&31)==0 and
            bl_target(b,pc+4)==FIRST and bl_target(c,pc+8)==SECOND and
            adrp_target(d,pc+12)==PAGE and (d&31)==8 and
            mem_x(e,False)==(8,0,DISP)):
        raise ValueError("983_CALL_AND_GLOBAL_CHAIN_DID_NOT_MATCH_ORIGINAL:"+hex(pc))
    return {"mov983_pc":hex(pc),"callee_1":hex(FIRST),"callee_2":hex(SECOND),
            "global_store_pc":hex(pc+16),"global_rva":hex(PAGE+DISP),
            "words_le":[code[pc-base+i*4:pc-base+i*4+4].hex() for i in range(5)],
            "grade":"DIRECT_INSTRUCTION_CHAIN_VERIFIED__TABLE_SEMANTICS_UNPROVEN"}

def find_xrefs(code,base):
    # Exact ADRP target plus up to 20 instructions of the same base register.
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    from capstone.arm64 import ARM64_OP_MEM
    from capstone import CS_GRP_JUMP,CS_GRP_CALL,CS_GRP_RET
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    md.detail=True
    refs=[]
    for off in range(0,len(code)&~3,4):
        pc=base+off
        w=struct.unpack_from("<I",code,off)[0]
        if adrp_target(w,pc)!=PAGE:continue
        base_reg=w&31
        for i in md.disasm(code[off+4:off+84],pc+4):
            if i.mnemonic in ("ldr","str") and len(i.operands)>=2:
                m=i.operands[1]
                if (m.type==ARM64_OP_MEM and
                    i.reg_name(m.mem.base).lower()=="x"+str(base_reg) and
                    m.mem.disp==DISP):
                    refs.append({"adrp_pc":hex(pc),"access_pc":hex(i.address),
                                 "operation":i.mnemonic,
                                 "assembly":i.mnemonic+" "+i.op_str,
                                 "grade":"ADRP_AND_EXACT_GLOBAL_DISP"})
            if (i.group(CS_GRP_JUMP) or i.group(CS_GRP_CALL) or i.group(CS_GRP_RET)):
                break
            _,writes=i.regs_access()
            if any(i.reg_name(r).lower() in
                   ("x"+str(base_reg),"w"+str(base_reg)) for r in writes):
                break
    return refs

def verify_indexed_lookup_table(code,base):
    """Byte-verify original indexed descriptor table, not an item record."""
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    from .trace_native_item_provenance import cmp_immediate
    cmp=cmp_immediate(readword(code,base,0x1445e3c))
    mov=readword(code,base,0x1445e50)
    adrp=readword(code,base,0x1445e44)
    add=readword(code,base,0x1445e48)
    ldr=readword(code,base,0x1445e58)
    d=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    madd=list(d.disasm(code[0x1445e54-base:0x1445e58-base],0x1445e54))
    if not (cmp and cmp["constant"]==0x4aa and cmp["compare_register"]==0 and
        movz_immediate(mov)==0x28 and (mov&31)==9 and
        adrp_target(adrp,0x1445e44)==0x3354000 and (adrp&31)==8 and
        (add&0xff000000)==0x91000000 and (add&31)==8 and
        ((add>>5)&31)==8 and ((add>>10)&0xfff)==0x500 and
        madd and madd[0].mnemonic=="umaddl" and
        madd[0].op_str.replace(" ","")=="x9,w0,w9,x8" and
        (ldr&0xffc00000)==0xb9400000 and (ldr&31)==9 and
        ((ldr>>5)&31)==9 and ((ldr>>10)&0xfff)*4==0x10):
        raise ValueError("ORIGINAL_983_INTERNAL_LOOKUP_LAYOUT_MISMATCH")
    return {"lookup_function_rva":hex(FIRST),
        "max_accepted_input_id":0x4aa,
        "indexed_slot_count_if_zero_based":0x4aa+1,
        "descriptor_stride":0x28,
        "table_base_rva":hex(0x3354500),
        "entry_word_offset":0x10,
        "verified_instructions":{
            "compare":"cmp w0, #0x4aa",
            "stride_load":"mov w9, #0x28",
            "index":"umaddl x9, w0, w9, x8",
            "field":"ldr w9, [x9, #0x10]"
        },
        "semantic_grade":"NATIVE_DESCRIPTOR_INDEX_LAYOUT_VERIFIED_NOT_LINKDATA_ID_983_PROVEN"}

def analyze(main,table):
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    sha=hashlib.sha256(main).hexdigest()
    tsha=hashlib.sha256(table).hexdigest()
    if sha!=MAIN_SHA or tsha!=ITEM_SHA:
        raise ValueError("NATIVE_NSO_OR_00983_SHA_MISMATCH")
    kind,sections=get_sections(main)
    if kind!="NSO0":raise ValueError("EXPECTED_NSO0")
    text=next(s for s in sections if s["name"]=="text")
    code,base=text["data"],text["mem_offset"]
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM);md.detail=True
    result={
        "status":"ORIGINAL_LITERAL983_RESOURCE_LOOKUP_LIKE_CHAIN__ITEM_IDENTITY_UNVERIFIED",
        "main_sha256":sha,"item_table_sha256":tsha,
        "literal_983_call_chains":[chain(code,base,pc) for pc in CALLERS],
        "global_rva":hex(PAGE+DISP),
        "native_index_descriptor_layout":verify_indexed_lookup_table(code,base),
        "global_xrefs":find_xrefs(code,base),
        "callee_disassembly":{
           hex(pc):windows(md,code,base,pc,before=16,after=136)
           for pc in (FIRST,SECOND)
        },
        "confirmed_983_is_original_linkdata_entry":False,
        "confirmed_original_00983_table_pointer":False,
        "confirmed_68_byte_record_consumer":False,
        "confirmed_category_enum":False,
        "confirmed_stack_limit":False,
        "limitation":"Exact instruction chain and global reference are proven. Proving this is the 00983 item record requires tracing loader semantics, global pointer use and 4600 x 68 dataflow."
    }
    result["global_xref_count"]=len(result["global_xrefs"])
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,default=Path("2.0.1/exefs/main"))
    p.add_argument("--item-table",type=Path,default=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin"))
    p.add_argument("--out",type=Path,default=OUT)
    a=p.parse_args()
    report=analyze(a.main.read_bytes(),a.item_table.read_bytes())
    a.out.mkdir(parents=True,exist_ok=True)
    (a.out/"literal983_global_provenance.json").write_text(json.dumps(
       report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("M11_3_CHAIN",json.dumps({
      "chains":report["literal_983_call_chains"],
      "descriptor_layout":report["native_index_descriptor_layout"],
      "global_rva":report["global_rva"],
      "xref_count":report["global_xref_count"],
      "xrefs":report["global_xrefs"][:24]},separators=(",",":")))
    for pc,asm in report["callee_disassembly"].items():
        print("M11_3_CALLEE",pc,json.dumps([r["pc"]+" "+r["assembly"]
                                           for r in asm],separators=(",",":")))

if __name__=="__main__":
    main()
