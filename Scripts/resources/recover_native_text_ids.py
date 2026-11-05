#!/usr/bin/env python3
"""M7 Pokopia native text-table parser and evidence-graded nine-language linker.

READ-ONLY. Text IDs are zero-based native record indices, not yet external
mission/scene IDs. Grouping proves structure alignment, not reference identity.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path

LANGS = ("jp","en","fr","it","de","es","zht","ko","zhs")
ANCHORS = (2323,2350,3304,4645)
FILE = re.compile(r"^\d{5}\.bin$")
MAX_STRING = 131072

def sha(data):
    return hashlib.sha256(data).hexdigest()

def u32(data, off):
    return struct.unpack_from("<I", data, off)[0]

@dataclass
class NativeTable:
    entry: int
    path: str
    sha: str
    count: int
    width: int
    version: int
    rows: list
    @property
    def forms(self): return 1 if self.width == 8 else 6
    @property
    def nonempty(self): return sum(any(row[0]) for row in self.rows)
    @property
    def bitmap(self): return sha(bytes(int(any(row[0])) for row in self.rows))
    @property
    def flaghash(self):
        return sha(b"".join(struct.pack("<I",r[2][0]) for r in self.rows)) if self.width == 8 else ""
    def key(self): return (self.count,self.width,self.bitmap,self.flaghash)

def parse(data, entry, path):
    if len(data) < 72: return None,"TOO_SMALL"
    count=u32(data,0)
    if not 1 <= count <= 200000 or data[8:64] != bytes(56):
        return None,"NON_TEXT_HEADER"
    first=u32(data,64)
    if first % count: return None,"INVALID_FIRST_POINTER"
    width=first//count
    if width not in (8,32): return None,"OTHER_LAYOUT"
    end=64+count*width
    if end >= len(data): return None,"TRUNCATED_INDEX"
    forms=1 if width==8 else 6
    rows=[]
    for i in range(count):
        base=64+i*width
        vals=[]
        offsets=[]
        for j in range(forms):
            field=base+4*j
            off=field+u32(data,field)
            if off < end or off >= len(data): return None,"INVALID_RELATIVE_POINTER"
            nul=data.find(b"\0",off,min(len(data),off+MAX_STRING+1))
            if nul < 0: return None,"MISSING_NUL"
            try: val=data[off:nul].decode("utf-8","strict")
            except UnicodeDecodeError: return None,"INVALID_UTF8"
            if val and sum(c.isprintable() or c in "\n\r\t" for c in val)/len(val) < 0.9:
                return None,"INVALID_PRINTABLE_RATIO"
            vals.append(val)
            offsets.append(off)
        meta=(u32(data,base+4),) if width==8 else (u32(data,base+24),u32(data,base+28))
        rows.append((tuple(vals),tuple(offsets),meta))
    return NativeTable(entry,path,sha(data),count,width,u32(data,4),rows),"PARSED"

def witness(table, kind):
    s="".join(v for row,_,_ in table.rows[:100] for v in row)
    if kind=="kana": return sum("\u3040"<=c<="\u30ff" for c in s)
    if kind=="hangul": return sum("\uac00"<=c<="\ud7af" for c in s)
    if kind=="han": return sum("\u3400"<=c<="\u9fff" for c in s)
    return 0

def groups_of_nine(tables):
    ids=sorted(tables)
    runs=[]
    i=0
    while i<len(ids):
        run=[ids[i]]
        i+=1
        while i<len(ids) and ids[i]==run[-1]+1 and tables[ids[i]].key()==tables[run[0]].key():
            run.append(ids[i]);i+=1
        runs.append(run)
    groups=[]
    ambiguous=[]
    for run in runs:
        t=tables[run[0]]
        if len(run)!=9 or t.count<2 or t.nonempty<2:
            if len(run)>9 or len(run)==9:
                ambiguous.append({"first_entry":run[0],"last_entry":run[-1],
                                  "file_count":len(run),"reason":"AMBIGUOUS_OR_LOW_CONTENT"})
            continue
        jp,_,_,_,_,_,zht,ko,zhs=(tables[x] for x in run)
        scripts=(witness(jp,"kana")>0 and witness(ko,"hangul")>0
                 and witness(zht,"han")>0 and witness(zhs,"han")>0)
        grade="STRUCTURE_AND_SCRIPT_WITNESS" if scripts else "STRUCTURE_ONLY"
        groups.append((run,grade))
    return groups,ambiguous

def write_csv(path,cols,rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=cols)
        writer.writeheader()
        writer.writerows(rows)

class Shard:
    def __init__(self,root,name,cols):
        self.root=root;self.name=name;self.cols=cols;self.part=-1;self.count=0
        self.file=None;self.writer=None;self.next()
    def next(self):
        if self.file:self.file.close()
        self.part+=1
        self.file=(self.root/f"{self.name}_{self.part:03d}.csv").open("w",encoding="utf-8",newline="")
        self.writer=csv.DictWriter(self.file,fieldnames=self.cols)
        self.writer.writeheader()
    def add(self,row):
        if self.file.tell()>32*1024*1024:self.next()
        self.writer.writerow(row);self.count+=1
    def close(self):self.file.close()


class JSONShard:
    """Write standards-compliant JSON arrays, sharded to avoid oversized blobs."""
    def __init__(self, root, name):
        self.root=root;self.name=name;self.part=-1;self.file=None
        self.current=0;self.count=0;self.next()
    def next(self):
        if self.file:
            self.file.write("\n]\n")
            self.file.close()
        self.part+=1
        self.current=0
        self.file=(self.root/f"{self.name}_{self.part:03d}.json").open("w",encoding="utf-8")
        self.file.write("[\n")
    def add(self, row):
        if self.current and self.file.tell()>32*1024*1024:self.next()
        if self.current:self.file.write(",\n")
        self.file.write(json.dumps(row,ensure_ascii=False))
        self.current+=1;self.count+=1
    def close(self):
        self.file.write("\n]\n")
        self.file.close()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--decoded-root",type=Path,required=True)
    ap.add_argument("--dest",type=Path,default=Path("UnPack/2.0.1/Resources/Localization/M7"))
    ap.add_argument("--max-file-mb",type=int,default=64)
    args=ap.parse_args()
    if not args.decoded_root.is_dir():ap.error("Decoded LINKDATA directory missing")
    root=args.dest;root.mkdir(parents=True,exist_ok=True)
    tables={}
    sources=[]
    for path in sorted(args.decoded_root.glob("*.bin")):
        if not FILE.fullmatch(path.name):continue
        entry=int(path.stem);size=path.stat().st_size
        if size>args.max_file_mb*1024*1024:
            sources.append(dict(entry=entry,path=path.as_posix(),bytes=size,sha256="",
                                status="SKIPPED_SIZE",record_count="",record_width="",
                                nonempty_rows="",bitmap_sha256="",metadata_sha256=""))
            continue
        data=path.read_bytes()
        table,status=parse(data,entry,path.as_posix())
        if table:tables[entry]=table
        sources.append(dict(entry=entry,path=path.as_posix(),bytes=size,sha256=sha(data),
                            status=status,record_count=table.count if table else "",
                            record_width=table.width if table else "",
                            nonempty_rows=table.nonempty if table else "",
                            bitmap_sha256=table.bitmap if table else "",
                            metadata_sha256=table.flaghash if table else ""))
    write_csv(root/"native_table_inventory.csv",
              ["entry","path","bytes","sha256","status","record_count","record_width",
               "nonempty_rows","bitmap_sha256","metadata_sha256"],sources)
    groups,ambiguous=groups_of_nine(tables)
    lookup={entry:(run[0],grade) for run,grade in groups for entry in run}
    gr=[]
    for run,grade in groups:
        first=tables[run[0]]
        gr.append(dict(start_entry=run[0],end_entry=run[-1],record_count=first.count,
                       forms=first.forms,evidence_grade=grade,category="UNKNOWN",
                       locale_order=",".join(LANGS),jp_kana=witness(tables[run[0]],"kana"),
                       ko_hangul=witness(tables[run[7]],"hangul"),
                       zht_han=witness(tables[run[6]],"han"),
                       zhs_han=witness(tables[run[8]],"han")))
    write_csv(root/"nine_language_groups.csv",
              ["start_entry","end_entry","record_count","forms","evidence_grade","category",
               "locale_order","jp_kana","ko_hangul","zht_han","zhs_han"],gr)
    write_csv(root/"ambiguous_runs.csv",["first_entry","last_entry","file_count","reason"],ambiguous)
    (root/"nine_language_groups.json").write_text(json.dumps(gr,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    raw=Shard(root,"native_records",
              ["entry","source_path","source_sha256","text_id","form_index","record_width",
               "absolute_byte_offset","raw_metadata","text","linked_group_start","link_grade"])
    for entry,t in sorted(tables.items()):
        group,grade=lookup.get(entry,("","UNLINKED_NATIVE_RECORD"))
        for text_id,(vals,offsets,metadata) in enumerate(t.rows):
            for form,(value,off) in enumerate(zip(vals,offsets)):
                raw.add(dict(entry=entry,source_path=t.path,source_sha256=t.sha,text_id=text_id,
                             form_index=form,record_width=t.width,absolute_byte_offset=off,
                             raw_metadata=";".join(f"0x{x:08x}" for x in metadata),
                             text=value,linked_group_start=group,link_grade=grade))
    raw.close()
    joined_json=JSONShard(root,"nine_language_records")
    joined=Shard(root,"nine_language_records",
                 ["start_entry","text_id","form_index","category","evidence_grade",
                  *LANGS,*(x+"_entry" for x in LANGS),*(x+"_offset" for x in LANGS)])
    for run,grade in groups:
        t=tables[run[0]]
        for text_id in range(t.count):
            for form in range(t.forms):
                row=dict(start_entry=run[0],text_id=text_id,form_index=form,
                         category="UNKNOWN",evidence_grade=grade)
                for lang,entry in zip(LANGS,run):
                    source=tables[entry]
                    row[lang]=source.rows[text_id][0][form]
                    row[lang+"_entry"]=entry
                    row[lang+"_offset"]=source.rows[text_id][1][form]
                joined.add(row)
                joined_json.add(row)
    joined.close()
    joined_json.close()
    found={run[0] for run,_ in groups}
    report=dict(status="M7_NATIVE_RECORDS_PARSED_UNVERIFIED_REFERENCES",
                input_files=len(sources),parsed_text_tables=len(tables),
                nine_language_groups=len(groups),native_record_forms_exported=raw.count,
                nine_language_rows_exported=joined.count, json_rows_exported=joined_json.count,
                ambiguous_runs=len(ambiguous),
                known_anchor_groups={str(x):("PASS" if x in found else "NOT_LINKED") for x in ANCHORS},
                id_semantics="ZERO_BASED_TABLE_RECORD_ORDINAL",
                category_evidence="NOT_YET_AVAILABLE",
                warnings=[
                    "Structural matching does not prove engine/script reference identity.",
                    "Forms 0..5 are raw slots, not verified grammatical meanings.",
                    "Locale assignments outside anchor groups are inferred from structure and script witness.",
                    "Unpaired native records have no assigned locale.",
                    "Category remains UNKNOWN without source reference evidence.",
                    "Only observed 8/32-byte table layouts parsed; other binary structures in inventory."])
    (root/"m7_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
