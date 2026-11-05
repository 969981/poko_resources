"""M9 exact KIDSOBJDB native IDOK container framing tests."""
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path
from Scripts.resources.m9_kidsobjdb_framing import decode_nodes, attach_to_graph


def synthetic():
    a=bytearray(136)
    a[:8]=b"_DOK0000"
    struct.pack_into("<I",a,8,28)
    struct.pack_into("<I",a,12,24)
    struct.pack_into("<I",a,16,2)
    struct.pack_into("<I",a,24,136)
    first=28
    a[first:first+8]=b"IDOK0000"
    struct.pack_into("<I",a,first+8,53)
    struct.pack_into("<I",a,first+16,0xC27BF870)
    second=84
    a[second:second+8]=b"IDOK0000"
    struct.pack_into("<I",a,second+8,52)
    struct.pack_into("<I",a,second+16,0xF7BEDF70)
    return a


class M9NativeFramingTests(unittest.TestCase):
    def test_two_nodes_lengths_padding_and_container_end(self):
        nodes,meta=decode_nodes(bytes(synthetic()),"root:demo")
        self.assertEqual(meta["declared_nodes"],2)
        self.assertEqual(meta["verified_nodes"],2)
        self.assertEqual(meta["final_offset"],136)
        self.assertEqual([n["record_start"] for n in nodes],[28,84])
        self.assertEqual([n["record_byte_length"] for n in nodes],[53,52])
        self.assertEqual([n["padding_bytes"] for n in nodes],[3,0])
        self.assertEqual(nodes[0]["raw_u32_at_offset_16"],"0xc27bf870")
        self.assertEqual(nodes[0]["field_schema"],"UNRESOLVED")

    def test_corrupt_padding_rejected(self):
        data=synthetic()
        data[81]=1
        with self.assertRaisesRegex(ValueError,"PADDING"):
            decode_nodes(bytes(data),"root:demo")

    def test_mismatched_header_count_rejected(self):
        data=synthetic()
        struct.pack_into("<I",data,16,3)
        with self.assertRaises(ValueError):
            decode_nodes(bytes(data),"root:demo")

    def test_sqlite_object_nodes_stay_untyped(self):
        data=synthetic()
        nodes,_=decode_nodes(bytes(data),"root:demo")
        with tempfile.TemporaryDirectory() as path:
            dbpath=Path(path)/"graph.sqlite"
            with sqlite3.connect(dbpath) as db:
                db.execute("CREATE TABLE native_sources (m3_record_id TEXT PRIMARY KEY)")
                db.execute("INSERT INTO native_sources VALUES (?)",("root:demo",))
            attach_to_graph(dbpath,nodes)
            with sqlite3.connect(dbpath) as db:
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM m3_kidsobjdb_records").fetchone()[0],2)
                self.assertEqual(db.execute(
                    "SELECT distinct field_schema FROM m3_kidsobjdb_records").fetchone()[0],"UNRESOLVED")
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("UPDATE m3_kidsobjdb_records SET field_schema='MISSION_ID'")

if __name__=="__main__":
    unittest.main()
