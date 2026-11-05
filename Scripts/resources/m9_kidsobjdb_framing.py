#!/usr/bin/env python3
"""Recover byte-exact KIDSOBJDB IDOK record framing from original Pokopia blobs.

This recovers structural record IDs and offsets. Header words are kept raw;
none is labeled a typed script/quest/localization foreign key without schema.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import sqlite3
import struct
from collections import Counter
from pathlib import Path


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def hash256(data):
    return hashlib.sha256(data).hexdigest()


def decode_nodes(data, source_id, max_nodes=1000000):
    if len(data)<28 or data[:8]!=b"_DOK0000":
        raise ValueError("NOT_KIDSOBJDB_CONTAINER")
    if u32(data,8)!=28 or u32(data,12)!=24:
        raise ValueError("UNSUPPORTED_KIDSOBJDB_HEADER")
    count=u32(data,16)
    declared_size=u32(data,24)
    if declared_size!=len(data):
        raise ValueError("KIDSOBJDB_SIZE_MISMATCH")
    if count<1 or count>max_nodes:
        raise ValueError("KIDSOBJDB_RECORD_COUNT_UNSUPPORTED")
    off=28
    rows=[]
    words=Counter()
    padding=Counter()
    for index in range(count):
        if off+32>len(data) or data[off:off+8]!=b"IDOK0000":
            raise ValueError(f"IDOK_SIGNATURE_OR_BOUNDARY_MISMATCH:index={index}:offset={off}")
        size=u32(data,off+8)
        if size<32 or off+size>len(data):
            raise ValueError(f"IDOK_LENGTH_OUT_OF_RANGE:index={index}:offset={off}:length={size}")
        end=off+size
        nextoff=(end+3)&~3
        if nextoff>len(data) or any(data[end:nextoff]):
            raise ValueError(f"IDOK_PADDING_NOT_ZERO:index={index}:offset={off}")
        word12=u32(data,off+12)
        word16=u32(data,off+16)
        word20=u32(data,off+20)
        word24=u32(data,off+24)
        word28=u32(data,off+28)
        words[f"0x{word16:08x}"]+=1
        padding[nextoff-end]+=1
        rows.append({
            "m3_record_id":source_id,
            "native_node_index":index,
            "record_start":off,
            "record_byte_length":size,
            "record_data_end":end,
            "next_aligned_start":nextoff,
            "padding_bytes":nextoff-end,
            "raw_u32_at_offset_12":f"0x{word12:08x}",
            "raw_u32_at_offset_16":f"0x{word16:08x}",
            "raw_u32_at_offset_20":f"0x{word20:08x}",
            "raw_u32_at_offset_24":f"0x{word24:08x}",
            "raw_u32_at_offset_28":f"0x{word28:08x}",
            "record_sha256":hash256(data[off:end]),
            "record_structural_evidence":"HEADER_COUNT_LENGTH_AND_ALIGNMENT_EXACT",
            "field_schema":"UNRESOLVED",
            "language_table_foreign_key":"NOT_PROVEN"})
        off=nextoff
    if off!=len(data):
        raise ValueError(f"KIDSOBJDB_TRAILING_OR_MISSING_NODES:offset={off}:size={len(data)}")
    return rows,{
        "declared_nodes":count,
        "verified_nodes":len(rows),
        "final_offset":off,
        "file_bytes":len(data),
        "padding_lengths":dict(sorted(padding.items())),
        "frequent_unknown_word_at_offset_16":dict(words.most_common(15)),
        "node_structural_status":"EXACT_NATIVE_FRAMING",
        "member_semantics":"UNRESOLVED",
        "external_text_references":"NOT_PROVEN"}


def write_csv(path, fields, rows):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def save_json(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def attach_to_graph(graph_path, nodes):
    if not graph_path.is_file():
        raise FileNotFoundError(graph_path)
    with sqlite3.connect(graph_path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS m3_kidsobjdb_records(
          m3_record_id TEXT NOT NULL,
          native_node_index INTEGER NOT NULL,
          record_start INTEGER NOT NULL,
          record_byte_length INTEGER NOT NULL,
          record_data_end INTEGER NOT NULL,
          next_aligned_start INTEGER NOT NULL,
          raw_u32_12 TEXT,
          raw_u32_16 TEXT,
          raw_u32_20 TEXT,
          raw_u32_24 TEXT,
          raw_u32_28 TEXT,
          record_sha256 TEXT NOT NULL,
          field_schema TEXT NOT NULL CHECK(field_schema='UNRESOLVED'),
          PRIMARY KEY(m3_record_id,native_node_index),
          FOREIGN KEY(m3_record_id) REFERENCES native_sources(m3_record_id)
        )""")
        db.execute("DELETE FROM m3_kidsobjdb_records")
        db.executemany(
            "INSERT INTO m3_kidsobjdb_records VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ((
                r["m3_record_id"],r["native_node_index"],
                r["record_start"],r["record_byte_length"],r["record_data_end"],
                r["next_aligned_start"],
                r["raw_u32_at_offset_12"],r["raw_u32_at_offset_16"],
                r["raw_u32_at_offset_20"],r["raw_u32_at_offset_24"],
                r["raw_u32_at_offset_28"],r["record_sha256"],r["field_schema"]
            ) for r in nodes))
        db.commit()
        actual=db.execute("SELECT count(*) FROM m3_kidsobjdb_records").fetchone()[0]
        if actual!=len(nodes):
            raise AssertionError(f"SQLite KIDSOBJDB native record count {actual} != {len(nodes)}")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sources",type=Path,required=True)
    p.add_argument("--unpack-root",type=Path,required=True)
    p.add_argument("--graph",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    args=p.parse_args()
    args.dest.mkdir(parents=True,exist_ok=True)
    with args.sources.open(encoding="utf-8",newline="") as f:
        src=list(csv.DictReader(f))
    if len(src)!=3:
        raise ValueError("Expected exactly three M3 evidence-backed sample files")
    all_rows=[]
    files=[]
    for s in sorted(src,key=lambda r:r["m3_record_id"]):
        if s["native_extension_hint"] if "native_extension_hint" in s else False:
            raise ValueError("Unexpected untrusted native_extension_hint column")
        path=args.unpack_root/s["output_path"]
        data=path.read_bytes()
        if hash256(data)!=s["output_sha256"]:
            raise ValueError("M3 sample SHA-256 changed")
        rows,report=decode_nodes(data,s["m3_record_id"])
        all_rows.extend(rows)
        files.append({
            "m3_record_id":s["m3_record_id"],
            "original_source":s["original_fdata"],
            "output_path":s["output_path"],
            "output_sha256":s["output_sha256"],
            "name_hash":s["name_hash"],
            "type_hash":s["type_hash"],
            **report})
    if not all_rows:
        raise ValueError("No native objects")
    columns=list(all_rows[0])
    write_csv(args.dest/"m3_kidsobjdb_native_records.csv",columns,all_rows)
    save_json(args.dest/"m3_kidsobjdb_native_framing.json",files)
    attach_to_graph(args.graph,all_rows)
    report={
        "status":"M9_KIDSOBJDB_NATIVE_RECORD_FRAMING_CONFIRMED",
        "files_source_verified":len(files),
        "native_node_records_verified":len(all_rows),
        "files":[{"m3_record_id":f["m3_record_id"],
                  "declared_nodes":f["declared_nodes"],
                  "verified_nodes":f["verified_nodes"],
                  "final_offset":f["final_offset"],
                  "file_bytes":f["file_bytes"]} for f in files],
        "sqlite_native_node_rows":len(all_rows),
        "field_type_semantics":"UNRESOLVED",
        "scene_quest_building_caller_foreign_keys":0,
        "evidence":"IDOK_COUNT_HEADER_AND_LENGTH_ALIGNMENT_EXACT",
        "warnings":[
            "A verified IDOK record boundary is not a decoded object member.",
            "The raw u32 words at offsets 12..28 are retained, not assigned false field names.",
            "No scene/quest/building text foreign key is inferred from native record numbering."
        ]}
    save_json(args.dest/"m9_object_framing_report.json",report)
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__":
    main()
