#!/usr/bin/env python3
"""M9.2 KIDSOBJDB typed field decode (layout validated by public parsers).

Source evidence: eArmada8/yumia_fdata_tools and
PieceMetal/DWOriginsAssetTool KidsObjectDatabase.
Property type and byte offset are real. Value-to-OID/hash coincidences are
NOT guaranteed semantic references, and none is promoted to localization FK.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

try:
    from .m9_kidsobjdb_framing import decode_nodes
except ImportError:
    from m9_kidsobjdb_framing import decode_nodes

SIZES={0:1,1:1,2:2,3:2,4:4,5:4,6:8,7:8,8:4,10:16,12:8,13:12}
F_COLS=("m3_record_id","native_node_index","object_id_hex","object_type_hash_hex",
        "property_index","property_name_hash_hex","property_type_code",
        "property_value_count","value_byte_offset","value_byte_length",
        "value_sha256","preview_hex","first_u32_values_json","evidence_grade")
C_COLS=("m3_record_id","native_node_index","property_index","property_name_hash_hex",
        "property_type_code","value_absolute_offset","source_object_id_hex",
        "value_u32_hex","candidate_target","target_native_node_index",
        "evidence_grade","is_verified_fk")


def sha(data): return hashlib.sha256(data).hexdigest()
def u32(data,p): return struct.unpack_from("<I",data,p)[0]
def hx(value): return f"0x{value:08x}"


class Shards:
    def __init__(self,root,prefix,columns,limit=24*1024*1024):
        self.root=root;self.prefix=prefix;self.cols=columns;self.limit=limit
        self.part=-1;self.file=None;self.writer=None;self.count=0
        self.open_next()
    def open_next(self):
        if self.file:self.file.close()
        self.part+=1
        self.file=(self.root/f"{self.prefix}_{self.part:03d}.csv").open(
            "w",encoding="utf-8",newline="")
        self.writer=csv.DictWriter(self.file,fieldnames=self.cols)
        self.writer.writeheader()
    def emit(self,row):
        if self.file.tell()>self.limit:self.open_next()
        self.writer.writerow(row)
        self.count+=1
    def close(self):
        self.file.close()


def parse_property_fields(data, nodes, m3_record_id, candidate_limit=100000):
    """Return typed fields and evidence-labelled candidates.

    The caller controls streaming; this generator does not materialize a
    potentially enormous table of 64-bit and vector property arrays.
    """
    oids={}
    for r in nodes:
        oid=u32(data,r["record_start"]+12)
        if oid in oids:
            raise ValueError(f"Duplicate native OID {hx(oid)} in {m3_record_id}")
        oids[oid]=r["native_node_index"]
    stats=Counter()
    histogram=Counter()
    possible=Counter()
    candidates_out=0
    for rec in nodes:
        start=rec["record_start"]
        end=rec["record_data_end"]
        oid=u32(data,start+12)
        type_hash=u32(data,start+16)
        n=u32(data,start+20)
        if n>4096:
            raise ValueError(f"Excessive property descriptors at native node {rec['native_node_index']}")
        descriptor_start=start+24
        cursor=descriptor_start+n*12
        if cursor>end:
            raise ValueError("IDOK descriptor range exceeds native record")
        for prop_index in range(n):
            desc=descriptor_start+prop_index*12
            prop_type=u32(data,desc)
            count=u32(data,desc+4)
            name_hash=u32(data,desc+8)
            if prop_type not in SIZES:
                raise ValueError(f"Unsupported property type {prop_type} in node {rec['native_node_index']}")
            value_bytes=SIZES[prop_type]*count
            if value_bytes>end-cursor:
                raise ValueError(f"Property value exceeds record at node {rec['native_node_index']}, member {prop_index}")
            raw=data[cursor:cursor+value_bytes]
            first=[]
            if prop_type in (4,5):
                for v in range(min(count,8)):
                    first.append(u32(data,cursor+4*v))
            field={
                "m3_record_id":m3_record_id,
                "native_node_index":rec["native_node_index"],
                "object_id_hex":hx(oid),
                "object_type_hash_hex":hx(type_hash),
                "property_index":prop_index,
                "property_name_hash_hex":hx(name_hash),
                "property_type_code":prop_type,
                "property_value_count":count,
                "value_byte_offset":cursor,
                "value_byte_length":value_bytes,
                "value_sha256":sha(raw),
                "preview_hex":raw[:12].hex(),
                "first_u32_values_json":json.dumps(first,separators=(",",":")),
                "evidence_grade":"NATIVE_TYPED_PROPERTY_BOUNDS_EXACT",
            }
            yield "field",field
            stats["typed_properties"]+=1
            histogram[prop_type]+=1
            if prop_type in (4,5):
                for v in range(count):
                    val=u32(data,cursor+4*v)
                    # Exact numeric match to a local object OID is a candidate
                    # relationship, not a proven edge without name/schema.
                    if val not in oids:continue
                    possible[hx(name_hash)]+=1
                    stats["typed_u32_local_oid_matches"]+=1
                    if candidates_out>=candidate_limit:continue
                    candidate={
                        "m3_record_id":m3_record_id,
                        "native_node_index":rec["native_node_index"],
                        "property_index":prop_index,
                        "property_name_hash_hex":hx(name_hash),
                        "property_type_code":prop_type,
                        "value_absolute_offset":cursor+4*v,
                        "source_object_id_hex":hx(oid),
                        "value_u32_hex":hx(val),
                        "candidate_target":"SAME_KIDSOBJDB_LOCAL_OBJECT_ID",
                        "target_native_node_index":oids[val],
                        "evidence_grade":"TYPED_U32_EQUALS_LOCAL_OID_UNVERIFIED_REFERENCE",
                        "is_verified_fk":0,
                    }
                    yield "candidate",candidate
                    candidates_out+=1
            cursor+=value_bytes
        if cursor!=end:
            raise ValueError(f"IDOK native value bytes mismatch: node={rec['native_node_index']} remaining={end-cursor}")
        stats["complete_node_properties"]+=1
    yield "stats",{
        "counts":dict(stats),
        "property_type_histogram":dict(sorted(histogram.items())),
        "candidate_property_hash_histogram":dict(possible.most_common(40)),
        "candidate_output_truncated":stats["typed_u32_local_oid_matches"]>candidates_out,
    }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources",type=Path,required=True)
    ap.add_argument("--unpack-root",type=Path,required=True)
    ap.add_argument("--dest",type=Path,required=True)
    args=ap.parse_args()
    args.dest.mkdir(parents=True,exist_ok=True)
    with args.sources.open(encoding="utf-8",newline="") as f:
        sources=list(csv.DictReader(f))
    if len(sources)!=3:raise ValueError("Expected three source-verified M3 KIDSOBJDB sample files")
    field_shards=Shards(args.dest,"native_typed_fields",F_COLS)
    candidates=Shards(args.dest,"unverified_local_oid_candidates",C_COLS)
    per_file=[]
    for r in sorted(sources,key=lambda x:x["m3_record_id"]):
        data=(args.unpack_root/r["output_path"]).read_bytes()
        if sha(data)!=r["output_sha256"]:
            raise ValueError("M3 native object provenance SHA differs")
        nodes,meta=decode_nodes(data,r["m3_record_id"])
        count=0
        probed=None
        for kind,value in parse_property_fields(data,nodes,r["m3_record_id"]):
            if kind=="field":
                field_shards.emit(value)
                count+=1
            elif kind=="candidate":
                candidates.emit(value)
            else:
                probed=value
        if probed is None or probed["counts"]["complete_node_properties"]!=len(nodes):
            raise ValueError("Native KIDSOBJDB property stream incomplete")
        per_file.append({
            "m3_record_id":r["m3_record_id"],
            "name_hash":r["name_hash"],
            "object_type_hash_m3":r["type_hash"],
            "source_sha256":r["output_sha256"],
            "verified_native_records":len(nodes),
            "verified_typed_property_fields":count,
            **probed,
        })
    field_shards.close()
    candidates.close()
    report={
        "status":"M9_NATIVE_TYPED_IDOK_PROPERTIES_EXACT",
        "source_kidsobjdb_files_verified":3,
        "native_node_records_verified":sum(x["verified_native_records"] for x in per_file),
        "native_typed_fields_exported":field_shards.count,
        "local_oid_equality_candidates_exported":candidates.count,
        "candidate_semantics":"NOT_PROVEN_FOREIGN_KEYS",
        "scene_quest_building_text_foreign_keys_confirmed":0,
        "files":per_file,
        "source_parsers":[
          "https://github.com/eArmada8/yumia_fdata_tools/blob/9d8dc1fb7436f14ffec42acb6d719cea1214abbd/ktid/yumia_decode_kidsobjdb.py",
          "https://github.com/PieceMetal/DWOriginsAssetTool/blob/22d744f37d4a55a7b684bd8c6d7fd14665c0152d/Core/KidsObjectDatabase.cs"
        ],
        "warnings":[
          "The on-disk property type and size are validated; their semantic names require a .name table or consumer code.",
          "A u32 value matching a local object ID is only a candidate relationship without a typed property name.",
          "Neither node index nor object ID is automatically an M7 text row ID.",
          "Files with unsupported native property types fail closed instead of silently skipping members."
        ]
    }
    (args.dest/"m9_typed_field_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
