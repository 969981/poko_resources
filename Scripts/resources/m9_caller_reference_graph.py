#!/usr/bin/env python3
"""M9: provenance-preserving M3 to M7 reference analysis.

M8 field-layout-backed edges are confirmed. Coincidental u32 matches in M3
KIDSOBJDB objects are strictly unverified candidates, never foreign keys.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sqlite3
import struct
from collections import Counter
from pathlib import Path

FIELDS = ("edge_id", "source_domain", "source_record_id", "source_entry",
          "source_field_offset", "field_type", "target_group_start",
          "target_text_id", "target_form_index", "category",
          "evidence_grade", "parser_evidence", "intermediates")
SOURCE_URL = "https://github.com/969981/PokoHex/blob/c71d2b73fb9d8cfe99c1067e6bfadfd19f60bf78/PokoHex.Parsing/"
TOKEN = re.compile(rb"(?i)(?<![A-Za-z0-9_])(?:MissionSettings|MissionInfo|mission|quest|script|dialogue|message|building|tutorial|texttable|textid)(?![A-Za-z0-9_])")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def emit_csv(path, cols, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def emit_json(path, obj):
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")


def getint(r,field):
    s=r.get(field,"")
    return None if s in ("",None) else int(s)


def typed_edges(m8, groups):
    items=read_csv(m8/"native_item_text_refs.csv")
    maps=read_csv(m8/"map_part_item_name_refs.csv")
    roles=read_csv(m8/"native_role_text_refs.csv")
    if len(items)!=4600 or len(roles)!=189:
        raise ValueError("Required M8 input counts differ")
    out=[]
    for r in items:
        row=getint(r,"target_text_id")
        if row is None: continue
        src=int(r["source_item_id"])
        off=int(r["source_field_offset"])
        if off!=64+src*68+34: raise ValueError("Item native field offset mismatch")
        group=int(r["target_group_start"])
        if group not in groups: raise ValueError("Missing M7 item text group")
        out.append(dict(zip(FIELDS,(
            f"item:{src}", "Item",src,983,off,"u16 item.name_index",
            group,row,0,"Items","NATIVE_TYPED_FIELD_PARSER",
            SOURCE_URL+"GameItemDumper.cs",""))))
    for r in maps:
        row=getint(r,"name_index")
        if row is None:continue
        src=int(r["source_record_id"])
        group=int(r["name_table_first_entry"])
        if group not in groups: raise ValueError("Missing M7 map-item name group")
        item_id=int(r["item_id"])
        item_off=int(r["item_name_index_offset"])
        if item_off!=64+item_id*68+34: raise ValueError("Map part item name offset mismatch")
        chain=json.dumps({
            "part_id":int(r["part_id"]),
            "part_item_id_offset":int(r["part_item_id_offset"]),
            "item_id":item_id,"item_name_index_offset":item_off},separators=(",",":"))
        out.append(dict(zip(FIELDS,(
            f"map-part:{src}","MapPartVariation",src,41,
            int(r["variation_part_id_offset"]),"u16 part_id -> item_id -> name_index",
            group,row,0,"MapParts","NATIVE_TYPED_CHAIN_PARSER",
            SOURCE_URL+"GameMapDumper.cs",chain))))
    for r in roles:
        if not any(r[lang] for lang in ("jp","en","fr","it","de","es","zht","ko","zhs")):
            continue
        role=r["category"]
        group=int(r["target_group_start"])
        if (role,group) not in (("Reactions",2332),("Skills",4942)):
            raise ValueError("Unknown M8 role table")
        src=int(r["entity_id"])
        out.append(dict(zip(FIELDS,(
            f"{role}:{src}",role,src,group,None,"native_role_record_id",
            group,int(r["target_text_id"]),0,role,"NATIVE_PINNED_ROLE_PARSER",
            SOURCE_URL+"GameAbilityDumper.cs",""))))
    if not out: raise ValueError("No independently verified native reference edges")
    return out


def m3_sources(path, wanted):
    hits={}
    count=0
    kinds=Counter()
    with path.open(encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            count+=1
            kinds[row["signature"]]+=1
            key=row["output_path"]
            if key in wanted:
                if key in hits: raise ValueError("Duplicate M3 source "+key)
                hits[key]=row
    if set(hits)!=wanted:
        raise ValueError("Missing M3 records: "+str(sorted(wanted-set(hits))))
    return hits,count,kinds


def examine(data, origin, m3, known):
    if not data.startswith(b"_DOK0000"):
        raise ValueError("KIDSOBJDB magic missing for "+origin)
    if m3["signature"]!="KIDSOBJDB_SIGNATURE":
        raise ValueError("M3 KIDSOBJDB provenance not confirmed")
    if struct.unpack_from("<I",data,24)[0]!=len(data):
        raise ValueError("KIDSOBJDB declared file size differs")
    nodes=[]
    pos=0
    while True:
        pos=data.find(b"IDOK0000",pos)
        if pos<0:break
        nodes.append(pos)
        pos+=8
    raw_matches=[]
    occurrences=Counter()
    for off in range(0,len(data)-3,4):
        val=struct.unpack_from("<I",data,off)[0]
        if val not in known:continue
        occurrences[val]+=1
        if len(raw_matches)<2000:
            raw_matches.append({
                "source_record":m3["record_id"],
                "source_path":origin,
                "source_byte_offset":off,
                "raw_u32":val,
                "possible_group_start":val,
                "text_id":"","category":"UNKNOWN",
                "field_type":"UNKNOWN",
                "caller":"UNKNOWN",
                "is_verified_fk":0,
                "evidence":"UNVERIFIED_NUMERIC_COINCIDENCE"})
    literal=[]
    for match in TOKEN.finditer(data):
        if len(literal)>=250:break
        literal.append({
            "source_record":m3["record_id"],"source_path":origin,
            "byte_offset":match.start(),"marker":match.group().decode("ascii"),
            "evidence":"UNVERIFIED_SOURCE_LITERAL"})
    return {"node_count":len(nodes),"node_offsets":nodes[:5000],
            "numeric_hits_total":sum(occurrences.values()),
            "numeric_hits_exported":len(raw_matches),
            "group_hits":dict(sorted(occurrences.items())),
            "literal_count":len(literal),
            "literal":literal,"numeric":raw_matches}


def sqlite_graph(path, edges, sources, candidates):
    if path.exists():path.unlink()
    db=sqlite3.connect(path)
    try:
        db.executescript("""
        CREATE TABLE native_sources(
          m3_record_id TEXT PRIMARY KEY, original_fdata TEXT,
          output_path TEXT, name_hash TEXT, type_hash TEXT,
          output_sha256 TEXT, source_bytes INTEGER);
        CREATE TABLE verified_edges(
          edge_id TEXT PRIMARY KEY, source_domain TEXT,
          source_record_id INTEGER, source_entry INTEGER,
          source_field_offset INTEGER, field_type TEXT,
          target_group_start INTEGER, target_text_id INTEGER,
          target_form_index INTEGER, category TEXT,
          evidence_grade TEXT, parser_evidence TEXT, intermediates TEXT);
        CREATE TABLE candidate_numeric_matches(
          source_record TEXT, source_byte_offset INTEGER,
          raw_u32 INTEGER, possible_group_start INTEGER,
          is_verified_fk INTEGER NOT NULL CHECK(is_verified_fk=0));
        CREATE INDEX ix_verified_target ON verified_edges(target_group_start,target_text_id);
        CREATE INDEX ix_candidate_table ON candidate_numeric_matches(possible_group_start);
        """)
        db.executemany("INSERT INTO verified_edges VALUES ("+",".join("?" for _ in FIELDS)+")",
                       (tuple(row[k] for k in FIELDS) for row in edges))
        db.executemany("INSERT INTO native_sources VALUES (?,?,?,?,?,?,?)",
                       ((s["m3_record_id"],s["original_fdata"],s["output_path"],
                         s["name_hash"],s["type_hash"],s["output_sha256"],
                         s["source_bytes"]) for s in sources))
        db.executemany("INSERT INTO candidate_numeric_matches VALUES (?,?,?,?,0)",
                       ((c["source_record"],c["source_byte_offset"],c["raw_u32"],
                         c["possible_group_start"]) for c in candidates))
        db.commit()
        if db.execute("SELECT count(*) FROM verified_edges").fetchone()[0]!=len(edges):
            raise AssertionError("Verified FK count differs")
    finally:
        db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--m3-index",type=Path,required=True)
    p.add_argument("--m7-groups",type=Path,required=True)
    p.add_argument("--m8-dir",type=Path,required=True)
    p.add_argument("--unpack-root",type=Path,required=True)
    p.add_argument("--sample",type=Path,action="append",required=True)
    p.add_argument("--dest",type=Path,required=True)
    args=p.parse_args()
    out=args.dest
    out.mkdir(parents=True,exist_ok=True)
    groups={int(row["start_entry"]) for row in read_csv(args.m7_groups)}
    if len(groups)!=179 or 4645 not in groups:raise ValueError("M7 group count/anchor mismatch")
    edges=typed_edges(args.m8_dir,groups)
    selection={}
    for path in args.sample:
        rel=path.resolve().relative_to(args.unpack_root.resolve()).as_posix()
        if rel in selection:raise ValueError("Sample file supplied twice")
        selection[rel]=path
    m3,n,kinds=m3_sources(args.m3_index,set(selection))
    sources=[]
    candidates=[]
    literals=[]
    nodes=[]
    summaries=[]
    for rel,path in sorted(selection.items()):
        info=m3[rel]
        data=path.read_bytes()
        checksum=digest(data)
        if info["output_sha256"]!=checksum:
            raise ValueError("M3 source SHA-256 mismatch "+rel)
        probe=examine(data,path.as_posix(),info,groups)
        sources.append({
            "m3_record_id":info["record_id"],"original_fdata":info["source_path"],
            "output_path":rel,"name_hash":info["name_hash"],
            "type_hash":info["type_hash"],"output_sha256":checksum,
            "source_bytes":len(data)})
        for off in probe["node_offsets"]:
            nodes.append({"source_record":info["record_id"],
                          "node_marker_offset":off,
                          "evidence":"IDOK_SIGNATURE_ONLY"})
        candidates.extend(probe["numeric"])
        literals.extend(probe["literal"])
        summaries.append({
            "m3_record_id":info["record_id"],"name_hash":info["name_hash"],
            "node_markers":probe["node_count"],
            "untyped_numeric_matches":probe["numeric_hits_total"],
            "literal_marker_count":probe["literal_count"],
            "raw_candidate_groups":probe["group_hits"]})
    emit_csv(out/"verified_resource_text_edges.csv",list(FIELDS),edges)
    emit_json(out/"verified_resource_text_edges.json",edges)
    emit_csv(out/"m3_object_sources.csv",
             ["m3_record_id","original_fdata","output_path","name_hash",
              "type_hash","output_sha256","source_bytes"],sources)
    emit_csv(out/"m3_object_node_signatures.csv",
             ["source_record","node_marker_offset","evidence"],nodes)
    emit_csv(out/"m3_literal_markers.csv",
             ["source_record","source_path","byte_offset","marker","evidence"],literals)
    emit_csv(out/"unverified_numeric_candidates.csv",
             ["source_record","source_path","source_byte_offset","raw_u32",
              "possible_group_start","text_id","category","field_type",
              "caller","is_verified_fk","evidence"],candidates)
    sqlite_graph(out/"localization_reference_graph.sqlite",edges,sources,candidates)
    report={
        "status":"M9_PARTIAL_TYPED_GRAPH_AND_UNVERIFIED_M3_PROBES",
        "m3_resources_indexed":n,
        "m3_type_signatures":dict(kinds.most_common(8)),
        "m7_groups_loaded":len(groups),
        "typed_foreign_keys_total":len(edges),
        "typed_edges_by_domain":dict(Counter(r["source_domain"] for r in edges)),
        "m3_kidsobjdb_objects_source_verified":len(sources),
        "raw_node_markers_exported":len(nodes),
        "unverified_numeric_candidates":len(candidates),
        "literal_markers_exported":len(literals),
        "sample_probes":summaries,
        "new_scene_quest_building_typed_foreign_keys":0,
        "m3_object_member_schema":"NOT_RESTORED",
        "script_callers":"NOT_VERIFIED",
        "untyped_matches_are_foreign_keys":False,
        "warnings":[
            "M3 type hash and native object header are not a typed field schema.",
            "An IDOK marker is not evidence of a typed node member or caller.",
            "Any u32 equal to an M7 table number in arbitrary native bytes is ONLY a candidate.",
            "M8 native typed references are reused; no scene/quest/building foreign keys were invented.",
            "Do not recategorize MapParts as Buildings based on object names or text."],
    }
    emit_json(out/"m9_report.json",report)
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
