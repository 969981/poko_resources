#!/usr/bin/env python3
"""M25.2: byte-verified inspection of 26 unmatched slots in native icon registry.

The original object B4A1803B contains a typed u32 property array of 3543
entries.  602 of its slots 429..1056 point to M19-proven source OIDs.
This script extracts 26 remaining original u32 values and looks them up in
all 678 ORIGINAL KIDSOBJDB databases. It does not assume they are sprites.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from collections import Counter,defaultdict
from pathlib import Path
from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

R=Path("UnPack/2.0.1/Resources")
OUT=R/"Villagers/Native_2.0.1/M25"
NATIVE=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native")
MAIN=NATIVE/"root_019167_50ae86ef.kidsobjdb"
M25=OUT/"m25_original_second_hop_kids_source_oid_backrefs.csv"
M19=R/"Pokemon/NativeCallers/M19/m19_verified_texture_object_edges.csv"
DB_SHA="86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541"
OWNER=0xB4A1803B
OWNER_TYPE=0x9D1AFA46
PROPERTY=0x34CBB458
START,END=429,1056

def read_csv(p):
    with p.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))

def out_csv(path,rows,headers):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=headers,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def inspect():
    src=MAIN.read_bytes()
    if hashlib.sha256(src).hexdigest()!=DB_SHA:
        raise ValueError("Original KIDSOBJDB texture-list SHA256 changed")
    _,objs=parse_kids(src)
    owner=objs.get(OWNER)
    if owner is None or owner["type"]!=OWNER_TYPE:
        raise ValueError("Original icon array owner type changed")
    prop=owner["fields"].get(PROPERTY)
    if prop is None or prop["kind"] not in (4,5) or prop["count"]!=3543:
        raise ValueError("Original icon array native record changed")
    prior=read_csv(M25)
    known={int(x["native_property_value_index"]):x for x in prior
           if x["original_source_file"]==MAIN.as_posix() and
              x["backref_source_node_oid"]==f"{OWNER:08x}"}
    if len(known)!=602 or any(not START<=idx<=END for idx in known):
        raise ValueError("M25 native array matching baseline changed")
    for k,row in known.items():
        p=prop["offset"]+4*k
        if (int(row["native_property_absolute_byte_offset"])!=p or
                struct.unpack_from("<I",src,p)[0]!=int(row["matched_M19_source_oid"],16)):
            raise ValueError(f"Original array M25 source does not match direct raw bytes at {k}")
    misses={idx:struct.unpack_from("<I",src,prop["offset"]+4*idx)[0]
            for idx in range(START,END+1) if idx not in known}
    if len(misses)!=26:
        raise ValueError(f"Unexpected number of original registry gaps: {len(misses)}")
    files=sorted(NATIVE.glob("*.kidsobjdb"))
    if len(files)!=678:raise ValueError("Not all original databases checked out")
    nodes=defaultdict(list)
    for path in files:
        blob=path.read_bytes()
        db,table=parse_kids(blob)
        for oid,rec in table.items():
            if oid not in misses.values():continue
            nodes[oid].append({
                "source":path.as_posix(),
                "sha256":db["source_sha256"],
                "object_offset":rec["offset"],
                "type_hash":f"{rec['type']:08x}",
                "fields":{
                    f"{h:08x}":{"kind":v["kind"],"count":v["count"],
                               "u32":f"{v['u32']:08x}" if v["u32"] is not None else "",
                               "absolute_byte_offset":v["offset"]}
                    for h,v in rec["fields"].items()},
            })
    m19=read_csv(M19)
    targets={int(row["source_object_hash"],16):row for row in m19}
    complete=[]
    gaprows=[]
    for idx in range(START,END+1):
        pos=prop["offset"]+4*idx
        value=struct.unpack_from("<I",src,pos)[0]
        before=known.get(idx-1)
        after=known.get(idx+1)
        kind=("original_icon_poke_block" if idx<743 else "original_icon_poke_uni_block")
        common={
            "native_array_index":idx,
            "original_owner_oid":f"{OWNER:08x}",
            "original_owner_type_hash":f"{OWNER_TYPE:08x}",
            "native_array_property_hash":f"{PROPERTY:08x}",
            "original_u32_byte_offset":pos,
            "original_u32":f"{value:08x}",
            "index_block":kind,
            "known_M19_source_oid":int(idx in known),
            "original_neighbor_previous_sprite":before["matched_M19_target_sprite_names"] if before else "",
            "original_neighbor_next_sprite":after["matched_M19_target_sprite_names"] if after else "",
            "source_oid_semantic_identity_verified":"",
            "game_villager_id_verified":"",
            "game_species_id_verified":"",
        }
        complete.append(common)
        if idx in known: continue
        possibilities=nodes.get(value,[])
        row={**common,
             "candidate_original_nodes_with_same_oid":len(possibilities),
             "candidate_node_original_sources":";".join(x["source"] for x in possibilities[:20]),
             "candidate_node_type_hashes":";".join(x["type_hash"] for x in possibilities[:20]),
             "candidate_node_fields_json":json.dumps(possibilities,ensure_ascii=False,separators=(",",":"))[:32000],
             "already_known_M19_source_oid":int(value in targets),
             "original_ref_status":("ZERO_PLACEHOLDER" if value==0 else
                ("ORIGINAL_NODE_PRESENT_REQUIRES_SEMANTICS" if possibilities else
                 "NO_NODE_WITH_THIS_OID_IN_678_ORIGINAL_KIDSDB")),
        }
        gaprows.append(row)
    by_status=Counter(x["original_ref_status"] for x in gaprows)
    report={
        "version":"2.0.1","original_source_file":MAIN.as_posix(),
        "original_source_sha256":DB_SHA,
        "original_owner_oid":f"{OWNER:08x}",
        "original_owner_type_hash":f"{OWNER_TYPE:08x}",
        "original_field_hash":f"{PROPERTY:08x}",
        "native_property_element_count":prop["count"],
        "native_array_element_first_byte_offset":prop["offset"],
        "inspected_index_range":[START,END],
        "original_pokemon_normal_range":[429,742],
        "original_pokemon_uni_range":[743,1056],
        "original_known_icon_source_oids_byte_verified":len(known),
        "original_unmatched_raw_slots":len(gaprows),
        "original_unmatched_indexes":[x["native_array_index"] for x in gaprows],
        "unmatched_original_u32_values":[x["original_u32"] for x in gaprows],
        "unmatched_raw_slot_statuses":dict(by_status),
        "original_database_scan_count":len(files),
        "native_species_id_bindings_verified":0,
        "native_villager_id_bindings_verified":0,
        "caveat":"Array index is not established as species or portrait ID. Missing known texture link is not proof of missing sprite, nor that the referenced OID is invalid.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    out_csv(OUT/"m25_2_full_628_native_icon_registry.csv",complete,list(complete[0]))
    out_csv(OUT/"m25_2_26_unmatched_native_icon_registry.csv",gaprows,list(gaprows[0]))
    (OUT/"m25_2_original_registry_summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report

def selftest():
    assert END-START+1==628
    assert 742-429+1==314
    assert 1056-743+1==314
    assert 628-602==26
    print("PASS source array block boundaries and coverage")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:selftest()
    else:inspect()

if __name__=="__main__":main()
