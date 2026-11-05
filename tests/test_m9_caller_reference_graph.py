"""M9 tests: verified resource edges never mix with raw numeric coincidences."""
import csv
import json
import sqlite3
import struct
import tempfile
import unittest
from pathlib import Path
from Scripts.resources.m9_caller_reference_graph import (
    FIELDS, examine, m3_sources, sqlite_graph, typed_edges, emit_csv
)


class M9Tests(unittest.TestCase):
    def sample(self):
        b=bytearray(144)
        b[:8]=b"_DOK0000"
        struct.pack_into("<I",b,24,len(b))
        b[28:36]=b"IDOK0000"
        struct.pack_into("<I",b,68,2350)
        b[88:103]=b"MissionSettings"
        return bytes(b)

    def test_untyped_numeric_never_becomes_foreign_key(self):
        m3={"record_id":"root:123","signature":"KIDSOBJDB_SIGNATURE"}
        p=examine(self.sample(),"synthetic.bin",m3,{2350,4645})
        self.assertEqual(p["node_count"],1)
        self.assertEqual(p["numeric_hits_total"],1)
        self.assertEqual(p["numeric"][0]["possible_group_start"],2350)
        self.assertEqual(p["numeric"][0]["is_verified_fk"],0)
        self.assertEqual(p["numeric"][0]["category"],"UNKNOWN")
        self.assertEqual(p["literal"][0]["marker"],"MissionSettings")
        self.assertEqual(p["literal"][0]["evidence"],"UNVERIFIED_SOURCE_LITERAL")

    def test_reject_unexpected_magic(self):
        m3={"record_id":"root:123","signature":"KIDSOBJDB_SIGNATURE"}
        with self.assertRaisesRegex(ValueError,"magic"):
            examine(bytes(64),"bad",m3,{2350})

    def test_m3_report_identity_is_exact_path(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"m3.csv"
            rows=[{"output_path":"romfs/pack/decoded/root_000123.bin",
                   "record_id":"root:123","signature":"KIDSOBJDB_SIGNATURE"}]
            emit_csv(path,list(rows[0]),rows)
            matches,total,hist=m3_sources(path,{"romfs/pack/decoded/root_000123.bin"})
            self.assertEqual(total,1)
            self.assertEqual(matches["romfs/pack/decoded/root_000123.bin"]["record_id"],"root:123")
            with self.assertRaisesRegex(ValueError,"Missing M3 records"):
                m3_sources(path,{"not-present.bin"})

    def test_sqlite_cannot_promote_raw_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"graph.sqlite"
            edge=dict(zip(FIELDS,("item:6","Item",6,983,506,"u16",
                4645,520,0,"Items","NATIVE_TYPED_FIELD_PARSER","unit","")))
            src={"m3_record_id":"root:10","original_fdata":"2.0.1/x.fdata",
                 "output_path":"romfs/x","name_hash":"abc","type_hash":"def",
                 "output_sha256":"sha","source_bytes":100}
            candidate={"source_record":"root:10","source_byte_offset":24,"raw_u32":2350,
                       "possible_group_start":2350}
            sqlite_graph(path,[edge],[src],[candidate])
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT count(*) FROM verified_edges").fetchone()[0],1)
                self.assertEqual(db.execute("SELECT count(*) FROM candidate_numeric_matches").fetchone()[0],1)
                self.assertEqual(db.execute("SELECT sum(is_verified_fk) FROM candidate_numeric_matches").fetchone()[0],0)
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("UPDATE candidate_numeric_matches SET is_verified_fk=1")

if __name__=="__main__":
    unittest.main()
