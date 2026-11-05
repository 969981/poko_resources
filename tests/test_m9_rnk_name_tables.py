"""M9.3 _RNK0000 parser and native KIDSOBJDB name-hash regression."""
import csv
import struct
import tempfile
import unittest
from pathlib import Path

from Scripts.resources.m9_rnk_name_tables import (
    candidate_paths, parse_dok_header, parse_rnk, scan_dok_property_identity,
)

def irnk(key, items):
    strings=[x.encode("utf-8")+b"\0" for x in items]
    p=20+len(items)*4
    offsets=[]
    raw=bytearray()
    for s in strings:
        offsets.append(p)
        raw.extend(s)
        p+=len(s)
    body=bytearray(b"IRNK0000")+struct.pack("<III",p,key,len(items))
    body+=b"".join(struct.pack("<I",v) for v in offsets)
    body+=raw
    return bytes(body)+bytes((-len(body))%4)

def rnk(records):
    body=b"".join(irnk(*x) for x in records)
    return b"_RNK0000"+struct.pack("<IIII",24,8,len(records),24+len(body))+body

def dok(name_hash,objects):
    parts=[]
    for oid,typ,props in objects:
        desc=b"".join(struct.pack("<III",5,len(v),h) for h,v in props)
        raw=b"".join(struct.pack("<I",num) for _,values in props for num in values)
        entry=bytearray(b"IDOK0000")
        entry+=struct.pack("<IIII",24+len(desc)+len(raw),oid,typ,len(props))
        entry+=desc+raw
        entry+=bytes((-len(entry))%4)
        parts.append(bytes(entry))
    body=b"".join(parts)
    return b"_DOK0000"+struct.pack("<IIIII",28,24,len(objects),name_hash,28+len(body))+body

class NameTableTests(unittest.TestCase):
    def test_explicit_owner_header_name_file_hash(self):
        binary=dok(0xA91711C6,[(0xAA,0x123,[(0xDD,[1,2])])])
        header=parse_dok_header(binary)
        self.assertEqual(header["native_object_count"],1)
        self.assertEqual(header["name_resource_hash"],"a91711c6")
        oids,props=scan_dok_property_identity(binary)
        self.assertEqual(oids,{0xAA})
        self.assertEqual(props[0xDD],1)
    def test_roundtrip_rnk_irnk_utf8_and_source_offsets(self):
        data=rnk([(0xAA,["SceneRoot","タイプ"]),(0xDD,["Name","Field"])])
        parsed,header=parse_rnk(data)
        self.assertEqual(header["entries"],2)
        self.assertEqual(parsed[0]["offset"],24)
        self.assertEqual(parsed[0]["key"],0xAA)
        self.assertEqual([x["text"] for x in parsed[0]["strings"]],["SceneRoot","タイプ"])
        self.assertEqual(parsed[1]["key"],0xDD)
        self.assertGreater(parsed[1]["offset"],parsed[0]["offset"])
    def test_unaligned_and_corrupt_string_offsets_fail_closed(self):
        data=bytearray(rnk([(1,["Hi","World"])]))
        struct.pack_into("<I",data,24+20,1)
        with self.assertRaisesRegex(ValueError,"INVALID_IRNK_STRING_OFFSETS"):
            parse_rnk(bytes(data))
    def test_forged_rnk_count_rejected(self):
        data=bytearray(rnk([(1,["hi"])]))
        struct.pack_into("<I",data,16,2)
        with self.assertRaises(ValueError):
            parse_rnk(bytes(data))
    def test_m3_candidate_lookup_exact_hash_no_fuzzy_match(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"index.csv"
            with path.open("w",encoding="utf8",newline="") as f:
                w=csv.DictWriter(f,fieldnames=["name_hash","output_path","record_id","type_hash"])
                w.writeheader()
                w.writerow({"name_hash":"a91711c6","output_path":"romfs/x/abc.bin","record_id":"root:2","type_hash":"bf6b52c7"})
                w.writerow({"name_hash":"a91711c7","output_path":"romfs/x/false.bin","record_id":"root:3","type_hash":"bf6b52c7"})
            rows,count=candidate_paths(path,{"a91711c6"})
            self.assertEqual(count,2)
            self.assertEqual(len(rows["a91711c6"]),1)
            self.assertEqual(rows["a91711c6"][0]["path"],"UnPack/2.0.1/romfs/x/abc.bin")
    def test_rnk_key_hash_is_not_assumed_property_name(self):
        # A native IRNK key that matches only the OBJECT id cannot be
        # promoted into property-name mapping without a schema witness.
        obj=dok(0xA91711C6,[(0xAA,0x123,[(0xBB,[1])])])
        ids,props=scan_dok_property_identity(obj)
        entries,_=parse_rnk(rnk([(0xAA,["An object"])]))
        self.assertIn(entries[0]["key"],ids)
        self.assertNotIn(entries[0]["key"],props)

if __name__=="__main__": unittest.main()
