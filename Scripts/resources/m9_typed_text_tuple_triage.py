#!/usr/bin/env python3
"""M9.13: native typed-field -> M7 group/row *coincidence* triage.

This enumerates two-field numeric hypotheses within one native KIDSOBJDB
node, validates exemplar raw bytes, and looks up nine-language text only
as candidate context. It does NOT recover script fields, real foreign keys
or quest/dialogue/building semantics. M8 verified edges remain unchanged.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
import struct
from pathlib import Path

LANGS=("jp","en","fr","it","de","es","zht","ko","zhs")
MAX_SAMPLES=500
NUMERIC_TYPES={"4","5"}
BASELINE=1_176_984
COLS=("source_m3_id","node_index","source_object_id","source_object_type_hash",
      "table_property_index","table_property_hash","table_property_type",
      "table_field_byte_offset","table_candidate_value","row_property_index",
      "row_property_hash","row_property_type","row_field_byte_offset",
      "row_candidate_value","m7_group_start","m7_record_count",
      "m7_evidence_grade","native_bytes_revalidated","m7_texts_form0_json",
      "evidence_grade","verified_script_caller","verified_text_fk","category")


def files_csv(paths):
    for p in paths:
        with p.open(encoding="utf-8-sig", newline="") as f:
            yield from csv.DictReader(f)


def groups_from_csv(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    if len(rows)<190:raise ValueError("M7 groups baseline incomplete")
    result={}
    for r in rows:
        n=int(r["start_entry"])
        if n in result or int(r["end_entry"])!=n+8 or int(r["record_count"])<1:
            raise ValueError("Invalid native M7 group identity")
        if r["category"]!="UNKNOWN" and n not in (2332,4942,4645):
            # M7 itself should not receive speculative semantic categories
            raise ValueError("M7 category changed; review native source graph")
        if tuple(r["locale_order"].split(","))!=LANGS:
            raise ValueError("Native M7 locale order changed")
        result[n]=r
    return result


def typed_scalar(row):
    if row["property_type_code"] not in NUMERIC_TYPES:
        return None
    if int(row["property_value_count"])!=1 or int(row["value_byte_length"])!=4:
        return None
    values=json.loads(row["first_u32_values_json"])
    if not isinstance(values,list) or len(values)!=1 or not isinstance(values[0],int):
        raise ValueError("Malformed typed native u32 value preview")
    return values[0]


def node_candidates(rows,groups):
    fields=[]
    for r in rows:
        value=typed_scalar(r)
        if value is None:continue
        fields.append((int(r["property_index"]),value,r))
    matches=[]
    for tindex,table,table_row in fields:
        group=groups.get(table)
        if group is None:continue
        count=int(group["record_count"])
        for rindex,row_value,row_row in fields:
            if rindex==tindex or abs(rindex-tindex)>3:
                continue
            if not (0<row_value<count):
                continue
            matches.append((table_row,row_row,table,group))
    return matches


def fill_candidate(table_row,row_row,group_start,group):
    return {
        "source_m3_id":table_row["m3_record_id"],
        "node_index":int(table_row["native_node_index"]),
        "source_object_id":table_row["object_id_hex"],
        "source_object_type_hash":table_row["object_type_hash_hex"],
        "table_property_index":int(table_row["property_index"]),
        "table_property_hash":table_row["property_name_hash_hex"],
        "table_property_type":int(table_row["property_type_code"]),
        "table_field_byte_offset":int(table_row["value_byte_offset"]),
        "table_candidate_value":group_start,
        "row_property_index":int(row_row["property_index"]),
        "row_property_hash":row_row["property_name_hash_hex"],
        "row_property_type":int(row_row["property_type_code"]),
        "row_field_byte_offset":int(row_row["value_byte_offset"]),
        "row_candidate_value":typed_scalar(row_row),
        "m7_group_start":group_start,
        "m7_record_count":int(group["record_count"]),
        "m7_evidence_grade":group["evidence_grade"],
        "native_bytes_revalidated":False,
        "m7_texts_form0_json":"",
        "evidence_grade":"TWO_TYPED_U32_SCALARS_NUMERIC_COINCIDENCE_ONLY",
        "verified_script_caller":False,
        "verified_text_fk":False,
        "category":"UNKNOWN",
    }


def analyze_typed_fields(paths,groups):
    samples=[]
    histogram=collections.Counter()
    scanned=0
    grouped_nodes=0
    current=None
    node=[]
    total_pairs=0
    def process_node():
        nonlocal total_pairs,grouped_nodes
        if not node:return
        grouped_nodes+=1
        for a,b,group_id,group in node_candidates(node,groups):
            total_pairs+=1
            histogram[(a["property_name_hash_hex"],b["property_name_hash_hex"],group_id)]+=1
            if len(samples)<MAX_SAMPLES:
                samples.append(fill_candidate(a,b,group_id,group))
    for row in files_csv(paths):
        scanned+=1
        key=(row["m3_record_id"],int(row["native_node_index"]))
        if current is not None and current!=key:
            process_node()
            node=[]
        current=key
        node.append(row)
    process_node()
    if scanned!=BASELINE:
        raise ValueError(f"Native typed field scan incomplete: {scanned} != {BASELINE}")
    return {
        "fields_scanned":scanned,
        "native_nodes_scanned":grouped_nodes,
        "unverified_group_row_numeric_tuples":total_pairs,
        "hypothesis_property_pair_histogram":[
            {"table_property_hash":k[0],"row_property_hash":k[1],
             "group_start":k[2],"count":v}
            for k,v in histogram.most_common(100)
        ],
    },samples


def validate_sample_source(samples,source_rows,root):
    src={r["m3_record_id"]:r for r in source_rows}
    if len(src)!=3:
        raise ValueError("Expected exactly 3 verified original KIDSOBJDBs")
    blobs={}
    for k,r in src.items():
        p=root/r["output_path"]
        data=p.read_bytes()
        if hashlib.sha256(data).hexdigest()!=r["output_sha256"]:
            raise ValueError("Native object bytes drifted from M9.2 SHA")
        blobs[k]=data
    for row in samples:
        data=blobs[row["source_m3_id"]]
        for prefix in ("table","row"):
            off=row[prefix+"_field_byte_offset"]
            if off<0 or off+4>len(data) or struct.unpack_from("<I",data,off)[0]!=row[prefix+"_candidate_value"]:
                raise ValueError("Typed field provenance numeric bytes changed")
        row["native_bytes_revalidated"]=True
    return {k:hashlib.sha256(blob).hexdigest() for k,blob in blobs.items()}


def add_m7_context(samples,native_rows):
    wanted={(row["m7_group_start"],row["row_candidate_value"],0) for row in samples}
    linked={}
    for row in files_csv(native_rows):
        key=(int(row["start_entry"]),int(row["text_id"]),int(row["form_index"]))
        if key not in wanted or key in linked:
            continue
        linked[key]={lang:row[lang] for lang in LANGS}
    for s in samples:
        key=(s["m7_group_start"],s["row_candidate_value"],0)
        # Text display is context for an unverified join, not reference proof.
        s["m7_texts_form0_json"]=json.dumps(linked.get(key,{}),ensure_ascii=False)
    return len(linked)


def run(field_files,m7_groups,m7_records,typed_report_path,m7_report_path,sources_path,
        original_root,dest):
    typed_report=json.loads(typed_report_path.read_text(encoding="utf-8"))
    m7report=json.loads(m7_report_path.read_text(encoding="utf-8"))
    if (typed_report["native_typed_fields_exported"]!=BASELINE or
        typed_report["local_oid_equality_candidates_exported"]!=87445 or
        typed_report["scene_quest_building_text_foreign_keys_confirmed"]!=0):
        raise ValueError("M9 typed evidence baseline changed")
    if m7report["nine_language_groups"]<190 or m7report["category_evidence"]!="NOT_YET_AVAILABLE":
        raise ValueError("M7 source classification has changed")
    groups=groups_from_csv(m7_groups)
    stats,samples=analyze_typed_fields(field_files,groups)
    with sources_path.open(encoding="utf-8-sig",newline="") as f:
        sources=list(csv.DictReader(f))
    source_hashes=validate_sample_source(samples,sources,original_root)
    contextualized=add_m7_context(samples,m7_records)
    dest.mkdir(parents=True,exist_ok=True)
    with (dest/"m9_numeric_text_tuple_samples.csv").open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=COLS)
        writer.writeheader()
        writer.writerows(samples)
    report={
        "status":"M9_TYPED_FIELD_TO_M7_NUMERIC_PAIR_TRIAGE_NOT_FOREIGN_KEYS",
        "m7_groups_loaded":len(groups),
        "m7_rows_looked_up_only_as_unverified_context":contextualized,
        "source_sha256":source_hashes,
        "samples_with_raw_byte_revalidation":sum(x["native_bytes_revalidated"] for x in samples),
        "example_limit":MAX_SAMPLES,
        "zero_row_id_hypotheses_excluded_for_noise_control":True,
        "unverified_local_oid_candidates_preserved":87445,
        "verified_script_to_text_foreign_keys":0,
        "new_quest_dialogue_building_classifications":0,
        "source_caller_schema_status":"NOT_RESTORED",
        "warnings":[
            "Two scalar words from one object do not establish a table selector and row selector.",
            "Native field type codes 4/5 are byte-width classes; u32 comparisons do not prove integer ID semantics.",
            "Nearby properties may be unrelated and M7 index overlap may be coincidental.",
            "Nine-language text is an optional contextual lookup, not proof the object ever displays it.",
            "No existing M8/M9 verified edges or UNKNOWN categories are modified.",
        ],
        **stats,
    }
    (dest/"m9_numeric_text_tuple_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="hypothesis_property_pair_histogram"},
                     ensure_ascii=False,indent=2))
    return report,samples


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--properties-dir",type=Path,required=True)
    p.add_argument("--m7-dir",type=Path,required=True)
    p.add_argument("--sources",type=Path,required=True)
    p.add_argument("--unpack-root",type=Path,required=True)
    p.add_argument("--dest",type=Path,required=True)
    a=p.parse_args()
    field_files=sorted(a.properties_dir.glob("native_typed_fields_*.csv"))
    records=sorted(a.m7_dir.glob("nine_language_records_*.csv"))
    if len(field_files)!=9 or len(records)<2:
        raise ValueError("Native typed-field or nine-language source shards are incomplete")
    run(field_files,a.m7_dir/"nine_language_groups.csv",records,
        a.properties_dir/"m9_typed_field_report.json",a.m7_dir/"m7_report.json",
        a.sources,a.unpack_root,a.dest)


if __name__=="__main__":
    main()
