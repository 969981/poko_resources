#!/usr/bin/env python3
"""M9.10: bounded native vtable-neighborhood references around M9.9 slots.

Recover ADRP+ADD / ADRP+LDR code references to *nearby address points*
rather than requiring an exact address to the callback slot. Every hit is
a static instruction-to-address candidate, NOT a proven indirect call.
No KIDSOBJDB field identity, script foreign key or M7 category is inferred.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
import struct
from pathlib import Path

from Scripts.resources.trace_native_species_item_callers import get_sections
from Scripts.resources.m9_rnk_exefs_xrefs import decode_adrp, decode_add, decode_load

SHA = "8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f"
WINDOW = 0x100
DISTANCES = (4, 8, 12, 16, 20, 24, 28, 32)
COLS = ("property_hash", "entry_callback", "pointer_slot", "address_point", "delta_from_slot",
        "adrp_pc", "consumer_pc", "instruction_kind", "distance_instructions", "adrp_word",
        "consumer_word", "evidence_grade", "vtable_address_point_confirmed",
        "indirect_runtime_call_confirmed", "script_text_fk_confirmed")


def u32(buffer, offset):
    return struct.unpack_from("<I", buffer, offset)[0]


def pointer_slots(doc):
    graph = doc["report"]
    if graph["source_exefs_sha256"] != SHA:
        raise ValueError("M9.9 hash baseline is incorrect")
    slots = {}
    for r in graph["static_pointer_slots"]:
        h = r["hash"]
        if h in slots or not any(q["is_entry"] and q["va"] == r["slot_va"] for q in r["surrounding_qwords"]):
            raise ValueError("Ambiguous native pointer evidence")
        slots[h] = (int(r["slot_va"]), int(r["entry_pc"]))
    if len(slots) != 3:
        raise ValueError("Expected exactly three native callback slots")
    return slots


def scan_neighborhood(code, base, pointers, window=WINDOW, max_hits=600):
    """Match nearby virtual addresses without assuming callback slot == vptr.

    Mask/decoder based. Requires literal ADRP register to be reused by LDR/ADD.
    Nonadjacent pairs are candidates even with a matching target, due to
    possible clobbering/branching between the two instructions.
    """
    page_to_slots = collections.defaultdict(list)
    for h, (slot, entry) in pointers.items():
        for page in range((slot-window) >> 12, ((slot+window) >> 12)+1):
            page_to_slots[page].append((h, slot, entry))
    rows = []
    counts = collections.Counter()
    for pos in range(0, len(code)-3, 4):
        pc = base+pos
        a = u32(code,pos)
        decoded = decode_adrp(a,pc)
        if decoded is None:
            continue
        page, base_register = decoded
        targets = page_to_slots.get(page >> 12)
        if not targets:
            continue
        for delta in DISTANCES:
            off=pos+delta
            if off+4 > len(code):
                break
            b=u32(code,off)
            op=None; address=None
            add=decode_add(b)
            if add is not None and add[0] == base_register:
                op="ADRP_ADD_ADDRESS";address=page+add[2]
            else:
                load=decode_load(b)
                if load is not None and load[0] == base_register:
                    op="ADRP_"+load[3];address=page+load[2]
            if address is None:
                continue
            for h,slot,entry in targets:
                if not (slot-window <= address <= slot+window):
                    continue
                if counts[h,op] >= max_hits:
                    continue
                counts[h,op]+=1
                rows.append({
                    "property_hash":h, "entry_callback":entry, "pointer_slot":slot,
                    "address_point":address, "delta_from_slot":address-slot,
                    "adrp_pc":pc, "consumer_pc":pc+delta,
                    "instruction_kind":op, "distance_instructions":delta//4,
                    "adrp_word":f"{a:08x}", "consumer_word":f"{b:08x}",
                    "evidence_grade":"ADJACENT_ARM64_ADDRESS_CONSTRUCTION" if delta==4 else "NONADJACENT_ARM64_ADDRESS_CANDIDATE",
                    "vtable_address_point_confirmed":False,
                    "indirect_runtime_call_confirmed":False,
                    "script_text_fk_confirmed":False,
                })
    rows.sort(key=lambda r:(r["property_hash"],r["delta_from_slot"],r["adrp_pc"],r["consumer_pc"]))
    return rows


def nearby_pointers(section, slot, radius=0x80):
    start=max(0, ((slot-section["mem_offset"]-radius)//8)*8)
    end=min(len(section["data"]), ((slot-section["mem_offset"]+radius+8)//8)*8)
    return [
        {"va": section["mem_offset"]+p,
         "u64":f"0x{struct.unpack_from('<Q',section['data'],p)[0]:016x}",
         "in_executable_text":struct.unpack_from("<Q",section["data"],p)[0] < 0x2749c00,
         "delta_from_slot": section["mem_offset"]+p-slot}
        for p in range(start,end,8) if p+8<=len(section["data"])
    ]


def analyze(main, previous):
    if hashlib.sha256(main).hexdigest()!=SHA:
        raise ValueError("Wrong original ExeFS build; refusing guessed pointers")
    kind, sections = get_sections(main)
    if kind!="NSO0":
        raise ValueError("Original Switch main must be NSO0")
    text = next(x for x in sections if x["name"]=="text")
    data = next(x for x in sections if x["name"]=="data")
    slots=pointer_slots(previous)
    for h,(slot,entry) in slots.items():
        off=slot-data["mem_offset"]
        if off<0 or off+8>len(data["data"]) or struct.unpack_from("<Q",data["data"],off)[0]!=entry:
            raise ValueError(f"Original callback pointer mismatch: {h}")
    rows=scan_neighborhood(text["data"],text["mem_offset"],slots)
    grouped=collections.Counter(r["property_hash"] for r in rows)
    report={
        "status":"M9_NATIVE_VTABLE_NEIGHBORHOOD_XREF_TRIAGE_ONLY",
        "original_exefs_sha256":SHA,
        "address_window_bytes_each_side":WINDOW,
        "scan_instruction_distances":list(DISTANCES),
        "static_address_candidates":len(rows),
        "per_hash":[{"property_hash":h,"entry_pc":entry,"slot_va":slot,
                     "nearby_reference_count":grouped[h],
                     "context_u64":nearby_pointers(data,slot)}
                    for h,(slot,entry) in sorted(slots.items())],
        "candidate_address_point_count":len({(r["property_hash"],r["address_point"]) for r in rows}),
        "verified_vtable_address_points":0,
        "verified_indirect_runtime_callers":0,
        "verified_KIDSOBJDB_property_getters":0,
        "new_scene_quest_building_text_foreign_keys":0,
        "limitations":[
            "Native data region pointer slots are real, but neighboring addresses need vptr construction/use proof.",
            "ADRP/LDR can fetch an arbitrary static value; it does not prove callback invocation.",
            "Nonadjacent ADRP uses may be register-clobbered across intervening instructions.",
            "New M7 text foreign keys are forbidden without typed resource field + native caller trace.",
        ],
    }
    return report,rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--pointer-evidence",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    a=p.parse_args()
    report,rows=analyze(a.main.read_bytes(),json.loads(a.pointer_evidence.read_text(encoding="utf-8")))
    a.dest.mkdir(parents=True,exist_ok=True)
    (a.dest/"exefs_vtable_neighborhood_report.json").write_text(
        json.dumps({"report":report,"xrefs":rows},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    with (a.dest/"exefs_vtable_neighborhood_xrefs.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=COLS);w.writeheader()
        w.writerows(rows)
    print(json.dumps({k:v for k,v in report.items() if k!="per_hash"},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
