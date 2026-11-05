#!/usr/bin/env python3
"""Chunk all 3,930 index-linked original miscellaneous Pokopia sprites.

Stable source key: original texinfo path, record index, G1T path and layer.
Plan and execution are separate so GitHub Actions can sparse-checkout exactly
one batch's native files. Never force failed files into "success" totals.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from Scripts.resources.export_native_misc_samples import export, read_index

ROOT=Path("UnPack/2.0.1/Resources/Textures")
KEYS=("texinfo_path","record_index","g1t_path","layer")
EXPECTED=3930


def key(row):
    return tuple(row[field] for field in KEYS)


def linked_rows(source):
    candidates=[row for row in source if row["status"]=="INDEXED_ORIGINAL_TEXINFO_G1T_PAIR"]
    if len(candidates)!=EXPECTED:
        raise ValueError(f"Expected {EXPECTED} verified index edges; got {len(candidates)}")
    candidates.sort(key=lambda x:key(x))
    keys=[key(x) for x in candidates]
    if len(set(keys))!=len(keys):
        raise ValueError("source-qualified sprite key collision: cannot partition safely")
    return candidates


def select_batch(source, batch, size):
    if not 1<=size<=480:
        raise ValueError("batch size must be 1..480")
    rows=linked_rows(source)
    total=(len(rows)+size-1)//size
    if not 0<=batch<total:
        raise ValueError(f"batch index {batch} out of range 0..{total-1}")
    return rows[batch*size:(batch+1)*size],total


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--batch",type=int,required=True)
    p.add_argument("--batch-size",type=int,default=240)
    p.add_argument("--index",type=Path,default=ROOT/"Indexes/native_misc_texture_index.csv")
    p.add_argument("--plan",type=Path,help="write ordered native rows for exact sparse checkout")
    p.add_argument("--read-plan",type=Path,help="execute an existing validated plan")
    args=p.parse_args()
    source=read_index(args.index)
    selected,total=select_batch(source,args.batch,args.batch_size)
    batch_name=f"batch_{args.batch:02d}"
    out=ROOT/"MiscNativeBatches"/batch_name
    if args.plan:
        args.plan.write_text(json.dumps({
            "batch_index":args.batch,"batch_size":args.batch_size,
            "total_batches":total,"total_indexed":EXPECTED,
            "index_sha256":hashlib.sha256(args.index.read_bytes()).hexdigest(),
            "rows":selected
        },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"batch":args.batch,"total_batches":total,
            "rows":len(selected),"distinct_sources":len(set(p for r in selected
            for p in (r["texinfo_path"],r["g1t_path"])))},ensure_ascii=False))
        return
    if args.read_plan:
        plan=json.loads(args.read_plan.read_text(encoding="utf-8"))
        expected_sha=hashlib.sha256(args.index.read_bytes()).hexdigest()
        if (plan["batch_index"]!=args.batch or plan["batch_size"]!=args.batch_size
                or plan["total_batches"]!=total or plan["index_sha256"]!=expected_sha
                or plan["rows"]!=selected):
            raise ValueError("batch plan does not match current original index")
    summary=export(selected,out)
    manifest=out/"misc_native_sample_manifest.csv"
    with manifest.open(encoding="utf-8",newline="") as f:
        records=list(csv.DictReader(f))
    if len(records)!=len(selected):
        raise ValueError(f"manifest lost {len(selected)-len(records)} source rows")
    if len(set((r["texinfo_path"],r["record_index"],r["g1t_path"],r["layer"])
               for r in records))!=len(selected):
        raise ValueError("output duplicated a source-qualified native record")
    good=sum(bool(r["png_path"]) for r in records)
    failed=[{"source_key":key(r),"status":r["status"],"reason":r["reason"]}
            for r in records if not r["png_path"]]
    statuses=dict(Counter(r["status"] for r in records))
    audit={
        "batch_id":args.batch,"batch_name":batch_name,"batch_size":args.batch_size,
        "total_batches":total,"source_scope_rows":EXPECTED,
        "indexed_rows_in_batch":len(selected),
        "png_success":good,"png_unavailable":len(failed),
        "statuses":statuses,
        "source_key_sha256":hashlib.sha256("\n".join("\t".join(key(r)) for r in selected).encode()).hexdigest(),
        "index_sha256":hashlib.sha256(args.index.read_bytes()).hexdigest(),
        "failed_source_rows":failed,
        "evidence":"Original TEXINFO + G1T, KIDSOBJDB index edge, Ounce decode, source UV, PNG/SHA verification",
        "identities_unverified":True,
    }
    (out/"batch_audit.json").write_text(json.dumps(audit,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in audit.items() if k!="failed_source_rows"},
                     indent=2,ensure_ascii=False))
    if good<1:
        raise ValueError(f"batch {args.batch} has zero actual PNG decodes")


if __name__=="__main__":
    main()
