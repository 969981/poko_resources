#!/usr/bin/env python3
"""Conservative ARM64 static probe of Pokopia 2.0.1 item fields and stack limits.

A load at +0x26 does not prove an item-record base; cmp #99 does not prove
the stack-merge path. Produces raw candidates only.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct
from trace_native_species_item_callers import get_sections

MAIN = Path("2.0.1/exefs/main")
OUT = Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS")
SHA256 = "8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
FIELDS = {0x08, 0x22, 0x26, 0x2a, 0x39, 0x3a, 0x41, 0x42}
LIMITS = {68, 99, 100, 255, 256, 4600}
LOADS = {0x39400000: ("ldrb",1), 0x79400000: ("ldrh",2),
         0xb9400000: ("ldr_w",4), 0xf9400000: ("ldr_x",8)}

def decode(word):
    opcode = word & 0xffc00000
    if opcode in LOADS:
        name, scale = LOADS[opcode]
        disp = ((word >> 10) & 0xfff) * scale
        if disp in FIELDS:
            return ("load",disp,name)
    if (word & 0xff00001f) in (0x7100001f, 0xf100001f):
        imm = ((word >> 10) & 0xfff) << (12 if (word >> 22) & 1 else 0)
        if imm in LIMITS:
            return ("cmp",imm,"cmp_x" if word >> 31 else "cmp_w")
    if (word & 0xff800000) in (0x52800000, 0xd2800000):
        imm = ((word >> 5) & 0xffff) << (((word >> 21) & 3) * 16)
        if imm in LIMITS:
            return ("movz",imm,"movz_x" if word >> 31 else "movz_w")
    return None

def self_test():
    assert decode(0x39400000 | (0x26<<10) | (1<<5)) == ("load",38,"ldrb")
    assert decode(0x79400000 | (0x3a//2<<10)) == ("load",58,"ldrh")
    assert decode(0xb9400000 | (0x08//4<<10)) == ("load",8,"ldr_w")
    assert decode(0x7100001f | (99<<10)) == ("cmp",99,"cmp_w")
    assert decode(0xf100001f | (100<<10)) == ("cmp",100,"cmp_x")
    assert decode(0x52800000 | (68<<5)) == ("movz",68,"movz_w")
    assert decode(0xd2800000 | (255<<5)) == ("movz",255,"movz_x")
    assert decode(0xd503201f) is None
    print("PASS: AArch64 unsigned immediate load / compare / movz fixtures")

def scan(code, base):
    counts = Counter()
    buckets = defaultdict(list)
    nearby = []
    for index,(word,) in enumerate(struct.iter_unpack("<I",code[:len(code)&~3])):
        item = decode(word)
        if item is None:
            continue
        name, number, op = item
        key = f"{name}:{number:#x}:{op}"
        counts[key] += 1
        pc = base + index*4
        if len(buckets[key]) < 120:
            buckets[key].append(pc)
        if name=="load" and number in (0x22,0x26,0x3a):
            nearby.append((pc,number))
    return counts,buckets,nearby

def asm(md,code,base,pc):
    offset=pc-base
    start=max(0,(offset-32)&~3)
    end=min(len(code),offset+64)
    return [{"pc":hex(x.address),"asm":x.mnemonic+" "+x.op_str}
            for x in md.disasm(code[start:end],base+start)]

def audit(blob):
    digest=hashlib.sha256(blob).hexdigest()
    if digest!=SHA256:
        raise ValueError("Wrong original ExeFS main SHA-256: "+digest)
    fmt, parts=get_sections(blob)
    if fmt!="NSO0":
        raise ValueError("Expected NSO0, got "+fmt)
    seg=next(p for p in parts if p["name"]=="text")
    code,base=seg["data"],seg["mem_offset"]
    counts,buckets,field_sites=scan(code,base)
    from capstone import Cs,CS_ARCH_ARM64,CS_MODE_ARM
    md=Cs(CS_ARCH_ARM64,CS_MODE_ARM)
    candidates=[]
    for k,pcs in sorted(buckets.items()):
        for pc in pcs[:24]:
            candidates.append({"instruction_key":k,"pc":hex(pc),
                               "context":asm(md,code,base,pc)})
    pairs=[]
    for i,(pc,field) in enumerate(field_sites):
        if field not in (0x26,0x3a):
            continue
        neighbors=[{"pc":hex(q),"field":hex(f)} for q,f in field_sites[max(0,i-24):i+25]
                   if q!=pc and f!=field and abs(q-pc)<=0x180]
        if neighbors:
            pairs.append({"pc":hex(pc),"field":hex(field),
                          "other_field_neighbors":neighbors[:10],
                          "status":"UNVERIFIED_SHARED_RECORD_BASE"})
    pairs.sort(key=lambda p:(-len(p["other_field_neighbors"]),int(p["pc"],16)))
    # Compare-to-field distance only; equality of basic block or register flow is NOT checked.
    limit_positions=[]
    for index,(word,) in enumerate(struct.iter_unpack("<I",code[:len(code)&~3])):
        d=decode(word)
        if d and d[0]=="cmp" and d[1] in (99,100):
            limit_positions.append((base+index*4,d[1]))
    from bisect import bisect_left,bisect_right
    field_pcs=[p for p,f in field_sites]
    limit_nearby=[]
    for limit_pc,constant in limit_positions:
        lo=bisect_left(field_pcs,limit_pc-0x100)
        hi=bisect_right(field_pcs,limit_pc+0x100)
        adjacent=[{"pc":hex(p),"offset":hex(f),"distance_bytes":abs(p-limit_pc)}
                  for p,f in field_sites[lo:hi] if f in (0x26,0x3a)]
        if adjacent:
            adjacent.sort(key=lambda x:x["distance_bytes"])
            limit_nearby.append({
                "cmp_pc":hex(limit_pc),"cmp_value":constant,
                "closest_candidate_loads":adjacent[:8],
                "status":"PROXIMITY_ONLY_NOT_PROVEN_QUANTITY_WRITEBACK"})
    limit_nearby.sort(key=lambda e:(e["closest_candidate_loads"][0]["distance_bytes"],int(e["cmp_pc"],16)))
    for e in limit_nearby[:18]:
        e["context"]=asm(md,code,base,int(e["cmp_pc"],16))

    for pair in pairs[:40]:
        pair["context"]=asm(md,code,base,int(pair["pc"],16))
    return {
      "status":"STATIC_OPCODE_CANDIDATES_NOT_PROVEN_CALLERS",
      "source":"2.0.1/exefs/main", "source_sha256":digest,
      "nso_format":fmt,"text_virtual_offset":hex(base),"text_bytes":len(code),
      "item_record_source":"UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin",
      "item_record_stride":68,
      "opcode_counts":dict(sorted(counts.items())),
      "sample_assembly":candidates,
      "cross_field_proximity":pairs[:90],
      "quantity_cmp_near_field":limit_nearby[:80],
      "official_category_enum_confirmed":False,
      "stack_merge_99_confirmed":False,
      "per_item_stack_override_confirmed":False,
      "bag_slot_capacity_confirmed":False,
      "limits":[
        "Raw instruction scanning only: signed/unscaled loads, register compares and values held in literal pools may be missed.",
        "NSO addresses are module-relative virtual offsets, not compressed file offsets.",
        "A field-offset match is not a verified 00983.bin consumer until base-register provenance is recovered.",
        "99/100/255 comparisons require inventory-specific caller chain and actual quantity writeback to count as proof."
      ]
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--main",type=Path,default=MAIN)
    parser.add_argument("--output",type=Path,default=OUT)
    parser.add_argument("--self-test",action="store_true")
    args=parser.parse_args()
    if args.self_test:
        self_test()
        return
    report=audit(args.main.read_bytes())
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"item_assembly_candidates.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    lines=[
        "# Pokopia 2.0.1 ExeFS original instruction candidates",
        "",
        "Source: 2.0.1/exefs/main",
        "SHA-256: "+report["source_sha256"],
        "Status: candidate only. No native field consumer or 99-stack limit proven.",
        "",
        "## Opcode counts (not semantic proof)",
        "",
    ]+[f"- {k}: {v}" for k,v in report["opcode_counts"].items()]+[
        "",
        "## Manual audit required",
        "",
        "1. Recover the producer of the base register at candidate +0x26/+0x3A loads.",
        "2. Tie it to item ID indexing and the 68-byte original item-record layout.",
        "3. Trace add/split/merge and quantity writeback for #99 or #100 comparison.",
        "4. Validate using gameplay examples in multiple item groups.",
        "Do not copy 99 to every item as an evidence-backed native max_stack field.",
        "",
    ]
    (args.output/"ITEM_ASSEMBLY_RESEARCH.md").write_text("\n".join(lines),encoding="utf-8")
    # Connector-readable shortlist; the full report is often too large to fetch.
    groups={
      "field_0x26_byte":lambda e:e["instruction_key"]=="load:0x26:ldrb",
      "field_0x3a_byte":lambda e:e["instruction_key"]=="load:0x3a:ldrb",
      "cmp_99":lambda e:e["instruction_key"] in ("cmp:0x63:cmp_w","cmp:0x63:cmp_x"),
      "cmp_100":lambda e:e["instruction_key"] in ("cmp:0x64:cmp_w","cmp:0x64:cmp_x"),
    }
    focus_report={
       "status":report["status"],
       "source_sha256":report["source_sha256"],
       "counts":report["opcode_counts"],
       "sample_instruction_windows":{name:[e for e in report["sample_assembly"] if check(e)][:3]
                                     for name,check in groups.items()},
       "closest_cmp_to_candidate_field":report["quantity_cmp_near_field"][:8],
       "cross_field_proximity":report["cross_field_proximity"][:5],
       "warning":"All PC pairs are proximity-only, not source register or gameplay stack-limit proof."
    }
    (args.output/"item_assembly_focus.json").write_text(
        json.dumps(focus_report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":report["status"],
       "source_sha256":report["source_sha256"],
       "text_bytes":report["text_bytes"],
       "opcode_counts":report["opcode_counts"],
       "proximity_groups":len(report["cross_field_proximity"])},indent=2))

if __name__=="__main__":
    main()
