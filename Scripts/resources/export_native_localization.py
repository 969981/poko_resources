#!/usr/bin/env python3
"""Export verified item translations and unverified native LINKDATA text candidates.

The only cross-language linkage assumed here is the previously validated item ID
catalog. All other extracted strings stay unaligned pending format analysis.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

LANGS = ("jp", "en", "fr", "it", "de", "es", "zht", "ko", "zhs")
ITEM_ENTRY = {"jp":4645, "en":4646, "fr":4647, "it":4648, "de":4649,
              "es":4650, "zht":4651, "ko":4652, "zhs":4653}
CONTROL = re.compile(r"<(?:\$[a-zA-Z]|oneline>|clear>|br>)")
FILE = re.compile(r"^(\d{5})\.bin$")
MAX_SIZE = 64 * 1024 * 1024
MAX_FRAGMENT = 32768

def save_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        out = csv.DictWriter(stream, fieldnames=fields)
        out.writeheader()
        out.writerows(rows)

def verified_items(catalog, validation, root):
    proof = json.loads(validation.read_text(encoding="utf-8"))
    if proof.get("status") != "MATCH" or proof.get("differences") != 0:
        raise RuntimeError("Native item names not verified")
    if any(proof["languages"][l].get("different") != 0 or
           proof["languages"][l].get("matched") != 4600 for l in LANGS):
        raise RuntimeError("Language slot validation failed")
    with catalog.open(encoding="utf-8-sig", newline="") as stream:
        items = list(csv.DictReader(stream))
    if len(items) != 4600 or [int(x["item_id"]) for x in items] != list(range(4600)):
        raise RuntimeError("Item ID catalog is not 4600 contiguous slots")
    for i, item in enumerate(items):
        for language in LANGS:
            if language not in item:
                raise RuntimeError("Missing locale "+language)
    rows = []
    for item in items:
        row = {"category":"Items", "text_id":int(item["item_id"]),
               "verification":"NATIVE_2_0_1_MATCH",
               "source_entry":983, "source_path":proof["source"]["items"]["path"]}
        for lang in LANGS:
            row[lang] = item[lang]
            row[lang+"_source_entry"] = ITEM_ENTRY[lang]
        rows.append(row)
    fields = ["category", "text_id", "verification", "source_entry", "source_path",
              *LANGS, *(l+"_source_entry" for l in LANGS)]
    save_csv(root/"verified_nine_language_items.csv", fields, rows)
    with (root/"verified_nine_language_items.json").open("w",encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return len(rows)

def scan(root, target, max_candidates):
    if not root.is_dir():
        raise FileNotFoundError(root)
    target.mkdir(parents=True, exist_ok=True)
    index_fields = ["entry_index", "source_path", "source_sha256", "byte_offset",
                    "utf8_bytes", "language", "text_id", "category",
                    "verification", "raw_text_with_tags"]
    index_path = target / "native_text_candidates.csv"
    sources_path = target / "native_source_inventory.csv"
    stats = {"files_total":0,"files_skipped_size":0,"files_with_tagged_text":0,
             "tagged_text_candidates":0,"truncated":False}
    with index_path.open("w",encoding="utf-8",newline="") as stream, \
         sources_path.open("w",encoding="utf-8",newline="") as inventory:
        writer=csv.DictWriter(stream, fieldnames=index_fields)
        writer.writeheader()
        sources=csv.writer(inventory)
        sources.writerow(["entry_index","source_path","size","sha256","status","candidates"])
        for path in sorted(root.glob("*.bin")):
            match=FILE.fullmatch(path.name)
            if not match:
                continue
            entry=int(match.group(1))
            stats["files_total"]+=1
            size=path.stat().st_size
            if size>MAX_SIZE:
                stats["files_skipped_size"]+=1
                sources.writerow([entry,path.as_posix(),size,"","SKIPPED_SIZE",0])
                continue
            data=path.read_bytes()
            digest=hashlib.sha256(data).hexdigest()
            cursor=0
            found=0
            for part in data.split(b"\x00"):
                offset=cursor
                cursor+=len(part)+1
                if len(part)<4 or len(part)>MAX_FRAGMENT or b"<" not in part:
                    continue
                try:
                    value=part.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                if not CONTROL.search(value) or not any(c.isalpha() for c in value):
                    continue
                if sum(c.isprintable() or c in "\n\r\t" for c in value)/len(value)<0.95:
                    continue
                writer.writerow({
                    "entry_index":entry,"source_path":path.as_posix(),
                    "source_sha256":digest,"byte_offset":offset,
                    "utf8_bytes":len(part),"language":"","text_id":"",
                    "category":"","verification":"UNVERIFIED_CANDIDATE",
                    "raw_text_with_tags":value
                })
                found+=1
                stats["tagged_text_candidates"]+=1
                if stats["tagged_text_candidates"]>=max_candidates:
                    stats["truncated"]=True
                    break
            if found:
                stats["files_with_tagged_text"]+=1
            sources.writerow([entry,path.as_posix(),size,digest,
                              "CANDIDATE" if found else "NO_TAGS",found])
            if stats["truncated"]:
                break
    return stats

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--decoded-root",type=Path,required=True)
    p.add_argument("--catalog",type=Path,default=Path("UnPack/2.0.1/Resources/Items/item_catalog.csv"))
    p.add_argument("--validation",type=Path,default=Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/validation.json"))
    p.add_argument("--dest",type=Path,default=Path("UnPack/2.0.1/Resources/Localization/Indexes"))
    p.add_argument("--max-candidates",type=int,default=200000)
    args=p.parse_args()
    if args.max_candidates<1:
        p.error("--max-candidates must be positive")
    args.dest.mkdir(parents=True,exist_ok=True)
    items=verified_items(args.catalog,args.validation,args.dest)
    stats=scan(args.decoded_root,args.dest,args.max_candidates)
    report={
        "status":"PARTIAL_NATIVE_LOCALIZATION_INDEX",
        "verified_item_ids":items,
        "verified_languages":list(LANGS),
        "unverified_native_scan":stats,
        "language_assignment_for_candidates":"UNKNOWN",
        "categories_for_candidates":"UNDETERMINED",
        "native_string_table_cross_language_links":"NOT_YET_PROVEN",
        "warnings":[
            "Item ID linkage is verified from existing native validation; dialogue/UI/quest/other links are not.",
            "Tagged UTF-8 zero-delimited candidate scan is not exhaustive.",
            "Output text IDs for candidates are empty until the native table format is decoded.",
            "An empty candidate result must not be interpreted as absent localization.",
            "Scan stops at candidate cap; skipped large files and truncated scans are reported."
        ]}
    (args.dest/"localization_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
