#!/usr/bin/env python3
"""Inspect all fields of original Pokopia v2.0.1 item table 00983.bin.

Outputs exact bytes, offsets and candidate categories without asserting any
material enum names. Independent M8 name-index validation is reused.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1")
SOURCE=Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
STRIDE=68
COUNT=4600
HEADER=64
# Only +0x22 is semantically verified (native item NameIndex).
# Other offsets below are empirical hypotheses; never silently rename them.
PROBE=(0x08,0x0C,0x10,0x14,0x18,0x1C,0x20,0x22,0x26,0x2A,0x2B,
       0x37,0x38,0x39,0x3A,0x3B,0x40,0x41,0x42,0x43)
FIELDS=["item_id","original_entry","record_file_offset","record_sha256",
        "record_hex_68","native_name_index","en_name","has_native_name",
        "raw_candidate_0x26_u8","raw_candidate_0x26_u16",
        "candidate_material_group_flag","semantic_classification_status",
        *[f"byte_0x{i:02X}" for i in range(STRIDE)]]
STATUS="RAW_FIELD_CANDIDATE_NO_NATIVE_ENUM_OR_CALLER_PROOF"


def parse(data: bytes, catalog):
    if len(data)!=HEADER+COUNT*STRIDE:
        raise ValueError("00983.bin header/record length mismatch")
    if struct.unpack_from("<II",data,0)!=(COUNT,3):
        raise ValueError("00983.bin original count/version mismatch")
    if len(catalog)!=COUNT:
        raise ValueError("native catalog lost item IDs")
    result=[]
    for i in range(COUNT):
        record=data[HEADER+i*STRIDE:HEADER+(i+1)*STRIDE]
        name_index=struct.unpack_from("<H",record,0x22)[0]
        x=catalog[i]
        if int(x["item_id"])!=i or int(x["native_name_index"])!=name_index:
            raise ValueError(f"item {i} NameIndex/native catalogue mismatch")
        candidate=record[0x26]
        result.append({
            "item_id":i,"original_entry":983,
            "record_file_offset":HEADER+i*STRIDE,
            "record_sha256":hashlib.sha256(record).hexdigest(),
            "record_hex_68":record.hex(),
            "native_name_index":name_index,
            "en_name":x["en"],"has_native_name":int(bool(x["en"])),
            "raw_candidate_0x26_u8":candidate,
            "raw_candidate_0x26_u16":struct.unpack_from("<H",record,0x26)[0],
            "candidate_material_group_flag":"PROBE_0X26_EQUALS_0X10" if candidate==0x10 else "",
            "semantic_classification_status":STATUS,
            **{f"byte_0x{p:02X}":record[p] for p in range(STRIDE)},
        })
    return result


def summary(rows,source_path,source_data):
    named=[r for r in rows if r["en_name"] and r["item_id"]!=0]
    hist=Counter(int(x["raw_candidate_0x26_u8"]) for x in rows)
    pairs=Counter((int(x["raw_candidate_0x26_u8"]),int(x["byte_0x2A"]))
                  for x in named)
    groups={}
    for k in sorted(hist):
        matching=[r for r in named if int(r["raw_candidate_0x26_u8"])==k]
        groups[str(k)]={"all_item_slots":hist[k],"with_native_names":len(matching),
            "name_examples":[{"id":r["item_id"],"name":r["en_name"]}
                             for r in matching[:15]]}
    # All 68 byte offsets are kept; lower-entropy fields are prioritized for
    # static xref search, not automatically declared enum/category.
    offsets=[]
    for off in range(STRIDE):
        values=Counter(int(r[f"byte_0x{off:02X}"]) for r in named)
        offsets.append({"offset":off,"hex_offset":f"0x{off:02X}",
                        "distinct_values":len(values),
                        "most_common":[{"value":v,"count":cnt}
                                       for v,cnt in values.most_common(6)]})
    return {
        "status":"NATIVE_BYTES_AND_NAME_INDEX_VALIDATED__TYPE_SEMANTICS_UNVERIFIED",
        "game_version":"2.0.1","entry_id":983,
        "original_path":str(source_path),"original_sha256":hashlib.sha256(source_data).hexdigest(),
        "record_header_bytes":HEADER,"record_stride_bytes":STRIDE,
        "record_count":len(rows),"named_item_count_excluding_empty":len(named),
        "verified_field":{"offset":34,"hex_offset":"0x22","width":2,
                          "meaning":"native item name_index; confirmed by all nine language tables"},
        "candidate_field":{"offset":38,"hex_offset":"0x26","width":1,
            "observed_for_raw_material_name_samples":16,
            "meaning":"UNKNOWN - group/category enum candidate, NOT confirmed material type"},
        "candidate_field_counts":groups,
        "named_pair_counts_0x26_vs_0x2A":[{"raw_0x26":a,"raw_0x2A":b,"count":n}
             for (a,b),n in pairs.most_common(80)],
        "byte_offset_profile":offsets,
        "native_material_item_ids_verified":0,
        "warning":"Material-type semantics require a native game field consumer or schema and positive/negative gameplay cases. Codes 0x10,0x0F,0x0A remain raw numeric evidence, not material classifications."
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--table",type=Path,default=SOURCE)
    p.add_argument("--catalog",type=Path,default=ROOT/"native_item_catalog.csv")
    p.add_argument("--output-dir",type=Path,default=ROOT)
    args=p.parse_args()
    with args.catalog.open(encoding="utf-8-sig",newline="") as f:
        names=list(csv.DictReader(f))
    original=args.table.read_bytes()
    rows=parse(original,names)
    args.output_dir.mkdir(parents=True,exist_ok=True)
    out=args.output_dir/"native_item_field_audit.csv"
    with out.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    report=summary(rows,args.table,original)
    (args.output_dir/"native_item_field_report.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("status","record_count",
        "named_item_count_excluding_empty","native_material_item_ids_verified",
        "candidate_field")},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
