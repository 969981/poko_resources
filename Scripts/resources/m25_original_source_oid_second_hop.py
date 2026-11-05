#!/usr/bin/env python3
"""M25: second-hop original typed KIDSOBJDB references to the 603 icon source OIDs.

Each hit is native KIDS property bytes and a checked target OID from M19.
This is a *raw typed-reference candidate*, not a species/villager ID mapping.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

ROOT=Path("UnPack/2.0.1/Resources")
NATIVE=Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native")
M19=ROOT/"Pokemon/NativeCallers/M19/m19_verified_texture_object_edges.csv"
OUT=ROOT/"Villagers/Native_2.0.1/M25"
VALID_KINDS={4,5}

def load_m19():
    with M19.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    if len(rows)!=603 or len(set(r["source_object_hash"] for r in rows))!=603:
        raise ValueError("Original M19 source OID set changed")
    for r in rows:
        if not(r["native_link_grade"]=="BYTE_VERIFIED_TYPED_OBJECT_HASH_EDGE__PROPERTY_SEMANTICS_UNVERIFIED"
               and r["source_type_hash"]=="79991e79"
               and r["source_g1t_hash"]=="00000000"
               and r["source_texinfo_hash"]=="00000000"
               and not r["native_species_id_verified"]):
            raise ValueError("Prior typed original source node changed")
    return {int(r["source_object_hash"],16):r for r in rows}

def scan_originals(files,targets):
    matches=[]
    scanned=0
    nodes_count=0
    typed_values=0
    types=Counter()
    found_target=set()
    for p in files:
        blob=p.read_bytes()
        _,nodes=parse_kids(blob)
        scanned+=1
        nodes_count+=len(nodes)
        sha=hashlib.sha256(blob).hexdigest()
        for oid,node in nodes.items():
            for prop_hash,prop in node["fields"].items():
                if prop["kind"] not in VALID_KINDS:continue
                # Native IDOK typed scalar/array u32, not arbitrary endian bytes.
                n=prop["count"]
                if n>100000:raise ValueError("Unsafe native array count")
                data_start=prop["offset"]
                if data_start<0 or data_start+n*4>len(blob):
                    raise ValueError("Native IDOK property bytes out of bounds")
                typed_values+=n
                for i in range(n):
                    at=data_start+4*i
                    value=struct.unpack_from("<I",blob,at)[0]
                    related=targets.get(value)
                    if related is None:continue
                    found_target.add(value)
                    types[f"{prop_hash:08x}"]+=1
                    matches.append({
                        "original_source_file":p.as_posix(),
                        "source_db_sha256":sha,
                        "backref_source_node_oid":f"{oid:08x}",
                        "backref_source_node_type_hash":f"{node['type']:08x}",
                        "backref_source_node_byte_offset":node["offset"],
                        "native_property_hash":f"{prop_hash:08x}",
                        "native_property_kind":prop["kind"],
                        "native_property_value_count":n,
                        "native_property_value_index":i,
                        "native_property_absolute_byte_offset":at,
                        "original_little_endian_u32":f"{value:08x}",
                        "matched_M19_source_oid":f"{value:08x}",
                        "matched_M19_target_icon_oid":related["target_object_hash"],
                        "matched_M19_target_sprite_names":related["target_sprite_names"],
                        "native_byte_evidence":"CHECKED_ORIGINAL_IDOK_U32_EQUALS_M19_TEXTURE_SOURCE_OID",
                        "game_villager_id_binding_verified":"",
                        "game_species_id_binding_verified":"",
                    })
    if scanned!=678:raise ValueError(f"Missing physical KIDS source coverage {scanned}!=678")
    return matches,{
        "original_kidsobjdb_files_scanned":scanned,
        "parsed_original_object_nodes":nodes_count,
        "typed_original_u32_values_scanned":typed_values,
        "M19_distinct_source_oids":len(targets),
        "original_typed_backreference_rows":len(matches),
        "distinct_M19_source_oids_referenced":len(found_target),
        "matched_property_hash_counts":dict(types.most_common()),
        "native_species_id_bindings_verified":0,
        "native_villager_id_bindings_verified":0,
        "warning":"A typed u32 match to an M19 source OID is only another raw reference candidate, not game identity. All original KIDSDB OIDs may be file-scoped or ambiguous.",
    }

def main_run():
    targets=load_m19()
    files=sorted(NATIVE.glob("*.kidsobjdb"))
    if len(files)!=678:raise ValueError("Not all 678 original source KIDSOBJDB files checked out")
    matches,report=scan_originals(files,targets)
    OUT.mkdir(parents=True,exist_ok=True)
    cols=("original_source_file","source_db_sha256","backref_source_node_oid",
          "backref_source_node_type_hash","backref_source_node_byte_offset",
          "native_property_hash","native_property_kind","native_property_value_count",
          "native_property_value_index","native_property_absolute_byte_offset",
          "original_little_endian_u32","matched_M19_source_oid",
          "matched_M19_target_icon_oid","matched_M19_target_sprite_names",
          "native_byte_evidence","game_villager_id_binding_verified","game_species_id_binding_verified")
    with (OUT/"m25_original_second_hop_kids_source_oid_backrefs.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows(matches)
    (OUT/"m25_original_second_hop_summary.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return report

def self_test():
    # Minimal raw _DOK0000 source with one IDOK having typed property
    # Native parser expects 28-byte _DOK header and 24+12+4 IDOK bytes.
    target={0x12345678:{"target_object_hash":"aabbccdd","target_sprite_names":"icon_poke_test"}}
    def mockblob(value):
        header=b"_DOK0000"+struct.pack("<5I",28,24,1,0,68)
        node=b"IDOK0000"+struct.pack("<4I",40,0xdeadbeef,0x79991e79,1)
        prop=struct.pack("<3I",5,1,0x2856a1b3)+struct.pack("<I",value)
        return header+node+prop
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as d:
        p=Path(d)/"tiny.kidsobjdb"
        p.write_bytes(mockblob(0x12345678))
        meta,nodes=parse_kids(p.read_bytes())
        assert nodes[0xdeadbeef]["fields"][0x2856a1b3]["u32"]==0x12345678
        assert len(p.read_bytes())==68
    print("PASS original KIDS typed scalar source parser")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test",action="store_true")
    a=p.parse_args()
    if a.self_test:self_test()
    else:main_run()

if __name__=="__main__":main()
