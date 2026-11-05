#!/usr/bin/env python3
"""Reconcile 17 source-qualified native PNG export batches without opening PNGs.

Every PNG has already passed hash/format checks inside its batch CI job.
This aggregator checks source coverage (3,930 indexed rows), uniqueness,
frozen source-index SHA, per-batch row counts, and failure transparency.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from Scripts.resources.export_native_misc_batches import linked_rows,key,EXPECTED

ROOT=Path("UnPack/2.0.1/Resources/Textures")
BATCH_ROOT=ROOT/"MiscNativeBatches"
FIELDS=["batch_id","texture_name","category_candidate","texinfo_hash","g1t_hash",
        "texinfo_path","record_index","layer","g1t_path","original_format",
        "canvas_width","canvas_height","layout","crop_box","crop_width","crop_height",
        "png_path","png_sha256","g1t_sha256","opaque_pixels","status","reason"]


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def reconcile(index,batchedir):
    source=linked_rows(index)
    index_keys={key(row) for row in source}
    found={}
    audits=[]
    status=Counter()
    absent_batches=[]
    png_paths=set()
    index_sha=None
    for batch in range(17):
        directory=batchedir/f"batch_{batch:02d}"
        af=directory/"batch_audit.json"
        mf=directory/"misc_native_sample_manifest.csv"
        if not (af.is_file() and mf.is_file()):
            absent_batches.append(batch)
            continue
        audit=json.loads(af.read_text(encoding="utf-8"))
        rows=read_csv(mf)
        expected=source[batch*240:(batch+1)*240]
        if audit["batch_id"]!=batch or audit["source_scope_rows"]!=EXPECTED:
            raise ValueError(f"batch_{batch:02d} changed source scope")
        if (audit["indexed_rows_in_batch"]!=len(expected) or
            len(rows)!=len(expected)):
            raise ValueError(f"batch_{batch:02d} missing source rows")
        if index_sha is None:
            index_sha=audit["index_sha256"]
        if index_sha!=audit["index_sha256"]:
            raise ValueError("index SHA changed between batches")
        rowhash=hashlib.sha256("\n".join("\t".join(key(r)) for r in expected).encode()).hexdigest()
        if audit["source_key_sha256"]!=rowhash:
            raise ValueError(f"batch_{batch:02d} source key digest mismatch")
        if [key(r) for r in rows]!=[key(r) for r in expected]:
            raise ValueError(f"batch_{batch:02d} changed row order or identity")
        count_good=count_missing=0
        for r in rows:
            k=key(r)
            if k not in index_keys or k in found:
                raise ValueError(f"duplicate/unindexed source key {k}")
            if r["png_path"]:
                count_good+=1
                if len(r["png_sha256"])!=64 or r["png_path"] in png_paths:
                    raise ValueError(f"bad or duplicate output PNG in {k}")
                png_paths.add(r["png_path"])
            else:
                count_missing+=1
                if not r["reason"]:
                    raise ValueError(f"failure row does not explain why {k}")
            found[k]={"batch_id":batch,**r}
            status[r["status"]]+=1
        if (count_good!=audit["png_success"] or count_missing!=audit["png_unavailable"]):
            raise ValueError(f"batch_{batch:02d} success/failure totals differ")
        audits.append({"batch_id":batch,"rows":len(rows),
                       "png_success":count_good,"png_unavailable":count_missing})
    missing_keys=index_keys-set(found)
    if len(missing_keys)!=sum(len(source[b*240:(b+1)*240]) for b in absent_batches):
        raise ValueError("missing rows do not match missing batch partitions")
    return {
       "game_version":"2.0.1","status":"COMPLETE_SOURCE_COVERAGE" if not absent_batches
              else "INCOMPLETE_BATCHES",
       "source_total":EXPECTED,"seen_source_records":len(found),
       "missing_source_records":len(missing_keys),"absent_batch_ids":absent_batches,
       "source_index_sha256":index_sha,
       "png_candidates":len(png_paths),
       "recorded_failure_rows":len(found)-len(png_paths),
       "status_counts":dict(status),"batch_results":audits,
       "source_key_uniqueness_checked":True,
       "material_types_proven":False,
       "species_ids_proven":False,
       "warning":"PNG candidates have source hashes and native UV. Material/gameplay identity and final pixel fidelity are separate evidence gates.",
    },[found[k] for k in sorted(found)]


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--index",type=Path,default=ROOT/"Indexes/native_misc_texture_index.csv")
    p.add_argument("--batches",type=Path,default=BATCH_ROOT)
    p.add_argument("--out",type=Path,default=ROOT/"Indexes")
    p.add_argument("--require-complete",action="store_true")
    args=p.parse_args()
    source=read_csv(args.index)
    report,rows=reconcile(source,args.batches)
    if report["source_index_sha256"] and report["source_index_sha256"]!=hashlib.sha256(args.index.read_bytes()).hexdigest():
        raise ValueError("batch index source SHA does not match current index")
    args.out.mkdir(parents=True,exist_ok=True)
    with (args.out/"native_misc_png_catalog.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    (args.out/"native_misc_png_summary.json").write_text(
        json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))
    if args.require_complete and report["status"]!="COMPLETE_SOURCE_COVERAGE":
        raise ValueError("not all 17 native sprite batches have committed results")


if __name__=="__main__":
    main()
