#!/usr/bin/env python3
"""M19: characterize typed native KIDS object -> Pokémon icon object edges.

The M17 property 0x2856a1b3 matches a target texture object hash.
Inspect both endpoint records, including source and target original bytes.
Do NOT conflate object hashes, filename numbers, or material categories with species IDs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import struct

from Scripts.resources.m16_verify_pokemon_texture_kidsobjdb import parse_kids

ROOT = Path("UnPack/2.0.1/Resources")
PACK = Path("UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native")
M17 = ROOT / "Pokemon/NativeCallers/M17/pokemon_typed_icon_oid_backrefs.csv"
CROSSWALK = ROOT / "Pokemon/pokemon_identity_crosswalk.csv"
OUT = ROOT / "Pokemon/NativeCallers/M19"
FIELD = 0x2856A1B3
G1T = 0xC8BB66DA
TEXINFO = 0x2276FC56
TYPE = 0x79991E79
COLS = (
    "original_source_file","source_file_sha256",
    "source_object_hash","source_type_hash","source_original_node_offset",
    "source_field_byte_offset","source_field_hash","source_g1t_hash",
    "source_texinfo_hash","source_known_icon_object",
    "target_object_hash","target_original_node_offset","target_type_hash",
    "target_g1t_hash","target_texinfo_hash","target_sprite_names",
    "same_object","source_and_target_g1t_identical","source_and_target_texinfo_identical",
    "native_link_grade","native_species_id_verified",
)


def read_csv(path: Path):
    with path.open(encoding="utf-8",newline="") as f:
        return list(csv.DictReader(f))


def scalar(props, key):
    v=props.get(key)
    return v["u32"] if v and v["kind"] in (4,5) and v["count"]==1 else None


def fmt(value):
    return f"{value:08x}" if value is not None else ""


def analyze(originals: dict[str, bytes], links: list[dict], crosswalk: list[dict]):
    if not links:
        raise ValueError("M17 has no links; refuse invented object relationships")
    indexes=defaultdict(list)
    for sprite in crosswalk:
        indexes[int(sprite["object_hash"],16)].append(sprite)
    expected_sources={str(PACK/"root_019167_50ae86ef.kidsobjdb"),
                      str(PACK/"root_053829_e2e43333.kidsobjdb")}
    if set(originals)!=expected_sources:
        raise ValueError("Unexpected original source set")
    native={}
    for source,blob in originals.items():
        metadata,nodes=parse_kids(blob)
        native[source]=(hashlib.sha256(blob).hexdigest(),nodes)
    rows=[]
    classes=Counter()
    for link in links:
        path=link["source_path"]
        if path not in native:
            raise ValueError("M17 row references unexpected source")
        sha,nodes=native[path]
        if link["source_db_sha256"]!=sha:
            raise ValueError("M17 recorded raw database SHA mismatch")
        source_oid=int(link["source_node_oid"],16)
        target_oid=int(link["matched_target_object_hash"],16)
        if source_oid not in nodes or target_oid not in nodes:
            raise ValueError("Missing one endpoint in original database")
        a=nodes[source_oid]; b=nodes[target_oid]
        if a["type"]!=TYPE or b["type"]!=TYPE:
            raise ValueError("Unexpected native typed object; cannot claim texture-object edge")
        field=a["fields"].get(FIELD)
        if not field or field["kind"] not in (4,5) or field["count"]!=1:
            raise ValueError("No expected original scalar link property")
        offset=int(link["native_property_absolute_byte_offset"])
        blob=originals[path]
        if offset!=field["offset"] or struct.unpack_from("<I",blob,offset)[0]!=target_oid:
            raise ValueError("M17 source offset does not contain exact target object hash")
        if source_oid==target_oid:
            raise ValueError("Unexpected self-edge: requires separate classification")
        sprites=indexes.get(target_oid,[])
        if not sprites:
            raise ValueError("Link target not a member of original Pokémon texture crosswalk")
        # Object property values are untyped resource hashes unless a native
        # consumer resolves their labels. Species IDs remain deliberately blank.
        src_g1t=scalar(a["fields"],G1T)
        src_tex=scalar(a["fields"],TEXINFO)
        dst_g1t=scalar(b["fields"],G1T)
        dst_tex=scalar(b["fields"],TEXINFO)
        if any(x is None for x in (src_g1t,src_tex,dst_g1t,dst_tex)):
            raise ValueError("One endpoint lacks exact G1T/TEXINFO hash fields")
        classes["same_g1t" if src_g1t==dst_g1t else "distinct_g1t"]+=1
        classes["same_texinfo" if src_tex==dst_tex else "distinct_texinfo"]+=1
        classes["source_is_other_icon" if source_oid in indexes else "source_not_in_icon_index"]+=1
        rows.append({
            "original_source_file":path,"source_file_sha256":sha,
            "source_object_hash":fmt(source_oid),"source_type_hash":fmt(a["type"]),
            "source_original_node_offset":a["offset"],
            "source_field_byte_offset":offset,"source_field_hash":fmt(FIELD),
            "source_g1t_hash":fmt(src_g1t),"source_texinfo_hash":fmt(src_tex),
            "source_known_icon_object":int(source_oid in indexes),
            "target_object_hash":fmt(target_oid),
            "target_original_node_offset":b["offset"],"target_type_hash":fmt(b["type"]),
            "target_g1t_hash":fmt(dst_g1t),"target_texinfo_hash":fmt(dst_tex),
            "target_sprite_names":";".join(x["texture_name"] for x in sprites),
            "same_object":0,
            "source_and_target_g1t_identical":int(src_g1t==dst_g1t),
            "source_and_target_texinfo_identical":int(src_tex==dst_tex),
            "native_link_grade":"BYTE_VERIFIED_TYPED_OBJECT_HASH_EDGE__PROPERTY_SEMANTICS_UNVERIFIED",
            "native_species_id_verified":"",
        })
    if len(rows)!=len(links):
        raise ValueError("Dropped typed original records")
    return rows,{
        "status":"TYPED_KIDS_OBJECT_TO_TEXTURE_OBJECT_EDGE_VERIFIED__SPECIES_UNRESOLVED",
        "original_source_count":len(originals),
        "m17_original_edges":len(links),
        "verified_distinct_object_edges":len(rows),
        "unique_source_oids":len(set(x["source_object_hash"] for x in rows)),
        "unique_target_oids":len(set(x["target_object_hash"] for x in rows)),
        "source_and_target_relationships":dict(classes),
        "source_hashes":{p:sha for p,(sha,_) in native.items()},
        "known_pokemon_icon_rows":len(crosswalk),
        "species_id_bindings_verified":0,
        "required_next_step":"Inspect the native consumer or original RNK property name of 0x2856a1b3 and then trace a separate species/variant key to the same object. A typed object-edge alone is not species identity."
    }


def selftest():
    try:
        analyze({},[],[])
        raise AssertionError("Accepted nonexistent native provenance")
    except ValueError:
        pass
    print("PASS empty original edges rejected")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,default=OUT)
    p.add_argument("--self-test",action="store_true")
    args=p.parse_args()
    if args.self_test:
        selftest()
        return
    links=read_csv(M17)
    sprites=read_csv(CROSSWALK)
    originals={str(p):p.read_bytes() for p in sorted(
        (PACK/"root_019167_50ae86ef.kidsobjdb",
         PACK/"root_053829_e2e43333.kidsobjdb"))}
    rows,summary=analyze(originals,links,sprites)
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/"m19_verified_texture_object_edges.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=COLS)
        writer.writeheader()
        writer.writerows(rows)
    (args.out/"m19_texture_object_edge_summary.json").write_text(
        json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
