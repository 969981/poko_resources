#!/usr/bin/env python3
"""M10: source-scoped, read-only Pokopia native evidence graph.

Python owns CSV and SQLite. This consumes M9's native-byte-verified ledger,
preserves its evidence grades, and never turns numeric equalities into foreign
keys or inferred item/category/stack semantics.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import struct
from collections import Counter
from pathlib import Path

ITEM_SHA = "2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f"
EXPECTED_ITEMS = 4600
HEADER = 64
STRIDE = 68
SOURCE = Path("UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin")
CATALOG = Path("UnPack/2.0.1/Resources/Items/Native_2.0.1/native_item_catalog.csv")
FIELDS = Path("UnPack/2.0.1/Resources/Localization/M9/Properties")

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE item_records (
 item_id INTEGER PRIMARY KEY,
 original_entry INTEGER NOT NULL CHECK(original_entry=983),
 record_offset INTEGER NOT NULL UNIQUE,
 record_sha256 TEXT NOT NULL,
 native_name_index INTEGER NOT NULL,
 en_name TEXT NOT NULL,
 raw_u8_26 INTEGER NOT NULL, raw_u8_3a INTEGER NOT NULL,
 raw_u32_08 INTEGER NOT NULL,
 verified_semantics TEXT NOT NULL CHECK(verified_semantics='NAME_INDEX_ONLY')
);
CREATE TABLE kids_sources (
 source_id TEXT PRIMARY KEY, original_sha256 TEXT NOT NULL,
 node_count INTEGER NOT NULL, field_count INTEGER NOT NULL
);
CREATE TABLE kids_nodes (
 source_id TEXT NOT NULL REFERENCES kids_sources(source_id),
 node_index INTEGER NOT NULL, raw_u32_12 TEXT NOT NULL,
 raw_u32_16 TEXT NOT NULL,
 PRIMARY KEY(source_id,node_index)
);
CREATE TABLE kids_fields (
 source_id TEXT NOT NULL, node_index INTEGER NOT NULL,
 property_index INTEGER NOT NULL, property_hash TEXT NOT NULL,
 type_code INTEGER NOT NULL, value_count INTEGER NOT NULL,
 value_byte_offset INTEGER NOT NULL, value_byte_length INTEGER NOT NULL,
 value_sha256 TEXT NOT NULL, first_u32_json TEXT NOT NULL,
 PRIMARY KEY(source_id,node_index,property_index),
 FOREIGN KEY(source_id,node_index) REFERENCES kids_nodes(source_id,node_index)
);
CREATE TABLE local_oid_equalities (
 source_id TEXT NOT NULL, source_node_index INTEGER NOT NULL,
 property_index INTEGER NOT NULL, value_absolute_offset INTEGER NOT NULL,
 target_node_index INTEGER NOT NULL, raw_target_oid TEXT NOT NULL,
 evidence TEXT NOT NULL CHECK(evidence='NUMERIC_EQUALITY_UNVERIFIED'),
 PRIMARY KEY(source_id,source_node_index,property_index,value_absolute_offset),
 FOREIGN KEY(source_id,source_node_index,property_index)
   REFERENCES kids_fields(source_id,node_index,property_index),
 FOREIGN KEY(source_id,target_node_index)
   REFERENCES kids_nodes(source_id,node_index)
);
CREATE TABLE item_id_equalities (
 source_id TEXT NOT NULL, node_index INTEGER NOT NULL,
 property_index INTEGER NOT NULL, property_hash TEXT NOT NULL,
 item_id INTEGER NOT NULL REFERENCES item_records(item_id),
 value_absolute_offset INTEGER NOT NULL,
 evidence TEXT NOT NULL CHECK(evidence='SCALAR_U32_EQUALS_ITEM_ID_UNVERIFIED'),
 PRIMARY KEY(source_id,node_index,property_index),
 FOREIGN KEY(source_id,node_index,property_index)
   REFERENCES kids_fields(source_id,node_index,property_index)
);
CREATE INDEX idx_kids_fields_hash ON kids_fields(property_hash,source_id);
CREATE INDEX idx_kids_oid ON kids_nodes(source_id,raw_u32_12);
CREATE INDEX idx_item_equality_id ON item_id_equalities(item_id,property_hash);
CREATE INDEX idx_item_equality_hash ON item_id_equalities(property_hash,source_id);
CREATE INDEX idx_local_oid_target ON local_oid_equalities(source_id,target_node_index);
"""


def rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def norm_hash(text: str) -> str:
    value = str(text).lower().removeprefix("0x")
    if len(value) != 8 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("INVALID_RAW_HEX32:" + str(text))
    return value


def parse_items(table: bytes, catalog: list[dict], expected_count=EXPECTED_ITEMS,
                expected_sha=ITEM_SHA):
    if expected_sha and hashlib.sha256(table).hexdigest() != expected_sha:
        raise ValueError("NATIVE_ITEM_TABLE_SHA_MISMATCH")
    if len(table) != HEADER + expected_count * STRIDE:
        raise ValueError("NATIVE_ITEM_TABLE_STRIDE_MISMATCH")
    if struct.unpack_from("<II", table) != (expected_count, 3):
        raise ValueError("NATIVE_ITEM_TABLE_HEADER_MISMATCH")
    if len(catalog) != expected_count:
        raise ValueError("NATIVE_ITEM_CATALOG_COUNT_MISMATCH")
    result = []
    for item_id, row in enumerate(catalog):
        at = HEADER + item_id * STRIDE
        record = table[at:at+STRIDE]
        name_index = struct.unpack_from("<H", record, 0x22)[0]
        if int(row["item_id"]) != item_id or int(row["native_name_index"]) != name_index:
            raise ValueError("NATIVE_NAME_INDEX_MISMATCH:" + str(item_id))
        result.append((item_id, 983, at, hashlib.sha256(record).hexdigest(), name_index,
                       row["en"], record[0x26], record[0x3a],
                       struct.unpack_from("<I", record, 8)[0], "NAME_INDEX_ONLY"))
    return result


def build(table_path: Path, catalog_path: Path, property_dir: Path,
          out: Path, expected_count=EXPECTED_ITEMS, expected_sha=ITEM_SHA):
    manifest_path = property_dir / "m9_typed_field_report.json"
    report = json.loads(manifest_path.read_text(encoding="utf-8"))
    if report["status"] != "M9_NATIVE_TYPED_IDOK_PROPERTIES_EXACT":
        raise ValueError("M9_ORIGINAL_REPORT_NOT_VERIFIED")
    source_metadata = {s["m3_record_id"]: s for s in report["files"]}
    if len(source_metadata) != report["source_kidsobjdb_files_verified"]:
        raise ValueError("M9_SOURCE_CARDINALITY_MISMATCH")
    files = sorted(property_dir.glob("native_typed_fields_*.csv"))
    if not files:
        raise ValueError("NO_M9_NATIVE_TYPED_FIELDS")
    edgefiles = sorted(property_dir.glob("unverified_local_oid_candidates_*.csv"))
    if not edgefiles:
        raise ValueError("NO_M9_LOCAL_OID_CANDIDATES")

    items = parse_items(table_path.read_bytes(), list(rows(catalog_path)),
                        expected_count, expected_sha)
    named_ids = {x[0] for x in items if x[5] and x[5] != "(Empty)"}
    out.mkdir(parents=True, exist_ok=True)
    database = out / "native_evidence_graph.sqlite"
    database.unlink(missing_ok=True)
    counts = Counter()
    per_file = Counter()
    per_source_nodes = {}
    matching_item_ids = set()
    with sqlite3.connect(database) as db:
        db.executescript(SCHEMA)
        db.executemany("INSERT INTO item_records VALUES (?,?,?,?,?,?,?,?,?,?)", items)
        db.executemany("INSERT INTO kids_sources VALUES (?,?,?,?)", [
            (k, s["source_sha256"], s["verified_native_records"],
             s["verified_typed_property_fields"]) for k, s in sorted(source_metadata.items())
        ])
        for path in files:
            for r in rows(path):
                source_id = r["m3_record_id"]
                if source_id not in source_metadata:
                    raise ValueError("UNKNOWN_M9_SOURCE:" + source_id)
                node = int(r["native_node_index"])
                oid = norm_hash(r["object_id_hex"])
                kind_hash = norm_hash(r["object_type_hash_hex"])
                key = (source_id, node)
                old = per_source_nodes.get(key)
                if old is None:
                    db.execute("INSERT INTO kids_nodes VALUES (?,?,?,?)",
                               (source_id, node, oid, kind_hash))
                    per_source_nodes[key] = (oid, kind_hash)
                elif old != (oid, kind_hash):
                    raise ValueError("INCONSISTENT_KIDS_NODE_METADATA:" + str(key))
                p = int(r["property_index"])
                type_code = int(r["property_type_code"])
                count = int(r["property_value_count"])
                value_offset = int(r["value_byte_offset"])
                value_length = int(r["value_byte_length"])
                if count < 0 or value_offset < 0 or value_length < 0:
                    raise ValueError("NEGATIVE_NATIVE_FIELD_BOUNDS")
                prop_hash = norm_hash(r["property_name_hash_hex"])
                sha = r["value_sha256"].lower()
                if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
                    raise ValueError("INVALID_PROPERTY_SHA256")
                first_u32 = json.loads(r["first_u32_values_json"])
                if not isinstance(first_u32, list):
                    raise ValueError("INVALID_U32_LIST")
                db.execute("INSERT INTO kids_fields VALUES (?,?,?,?,?,?,?,?,?,?)",
                           (source_id, node, p, prop_hash, type_code, count,
                            value_offset, value_length, sha,
                            json.dumps(first_u32, separators=(",", ":"))))
                counts["kids_fields"] += 1
                per_file[source_id] += 1
                # A scalar numerical coincidence is a hypothesis, never a typed FK.
                # Exclude zero/unnamed ID, floats, arrays and vector representations.
                if type_code in (4, 5) and count == 1 and len(first_u32) == 1:
                    value = int(first_u32[0])
                    if value in named_ids:
                        db.execute("INSERT INTO item_id_equalities VALUES (?,?,?,?,?,?,?)",
                                   (source_id, node, p, prop_hash, value, value_offset,
                                    "SCALAR_U32_EQUALS_ITEM_ID_UNVERIFIED"))
                        counts["item_id_numeric_equalities"] += 1
                        matching_item_ids.add(value)
        for source_id, s in source_metadata.items():
            actual_nodes = sum(k[0] == source_id for k in per_source_nodes)
            if actual_nodes != s["verified_native_records"] or per_file[source_id] != s["verified_typed_property_fields"]:
                raise ValueError("M9_NATIVE_LEDGER_CARDINALITY_MISMATCH:" + source_id)
        if counts["kids_fields"] != report["native_typed_fields_exported"]:
            raise ValueError("M9_FIELD_COUNT_MISMATCH")

        for path in edgefiles:
            for r in rows(path):
                source_id = r["m3_record_id"]
                src_node, target = int(r["native_node_index"]), int(r["target_native_node_index"])
                p = int(r["property_index"])
                offset = int(r["value_absolute_offset"])
                prop_hash = norm_hash(r["property_name_hash_hex"])
                value = norm_hash(r["value_u32_hex"])
                src_oid = norm_hash(r["source_object_id_hex"])
                if int(r["is_verified_fk"]) != 0 or r["evidence_grade"] != "TYPED_U32_EQUALS_LOCAL_OID_UNVERIFIED_REFERENCE":
                    raise ValueError("INAPPROPRIATE_M9_FK_GRADE")
                field = db.execute(
                    "SELECT property_hash,type_code,value_byte_offset,value_byte_length "
                    "FROM kids_fields WHERE source_id=? AND node_index=? AND property_index=?",
                    (source_id, src_node, p)).fetchone()
                if field is None or field[0] != prop_hash or field[1] not in (4, 5) or (
                    offset < field[2] or offset+4 > field[2]+field[3] or (offset-field[2])%4
                ):
                    raise ValueError("M9_LOCAL_OID_SOURCE_FIELD_MISMATCH")
                source_oid = db.execute(
                    "SELECT raw_u32_12 FROM kids_nodes WHERE source_id=? AND node_index=?",
                    (source_id, src_node)).fetchone()
                target_oid = db.execute(
                    "SELECT raw_u32_12 FROM kids_nodes WHERE source_id=? AND node_index=?",
                    (source_id, target)).fetchone()
                if not source_oid or not target_oid or source_oid[0] != src_oid or target_oid[0] != value:
                    raise ValueError("M9_LOCAL_OID_TARGET_MISMATCH")
                db.execute("INSERT INTO local_oid_equalities VALUES (?,?,?,?,?,?,?)",
                           (source_id, src_node, p, offset, target, value,
                            "NUMERIC_EQUALITY_UNVERIFIED"))
                counts["local_oid_numeric_equalities"] += 1
        if counts["local_oid_numeric_equalities"] != report["local_oid_equality_candidates_exported"]:
            raise ValueError("M9_LOCAL_OID_CANDIDATE_COUNT_MISMATCH")
        counts["kids_nodes"] = len(per_source_nodes)
        counts["items"] = len(items)
        top = db.execute(
            "SELECT property_hash,COUNT(*) AS hits,COUNT(DISTINCT item_id) AS distinct_items, "
            "COUNT(DISTINCT source_id) AS sources "
            "FROM item_id_equalities GROUP BY property_hash "
            "ORDER BY distinct_items DESC,hits DESC,property_hash LIMIT 60").fetchall()
        ranking = [{"property_hash": "0x"+h, "raw_equalities":hits,
                    "distinct_named_item_ids":different, "source_files":sources,
                    "evidence": "SCALAR_U32_EQUALS_ITEM_ID_UNVERIFIED"}
                   for h,hits,different,sources in top]
        # Evidence-only aggregate; no field is assigned a gameplay category here.
        summary = {
            "status": "NATIVE_PROVENANCE_GRAPH_BUILT",
            "item_table_source_sha256": hashlib.sha256(table_path.read_bytes()).hexdigest(),
            "item_id_to_kids_field_semantic_foreign_keys_verified": 0,
            "material_type_enum_verified": False,
            "max_stack_field_verified": False,
            "inventory_capacity_field_verified": False,
            "source_kidsobjdb_files": len(source_metadata),
            "source_sha256_verified_by_upstream_m9": True,
            "native_nodes": counts["kids_nodes"], "native_fields": counts["kids_fields"],
            "native_item_records": counts["items"],
            "local_oid_numeric_equality_candidates": counts["local_oid_numeric_equalities"],
            "item_id_scalar_numeric_equality_candidates": counts["item_id_numeric_equalities"],
            "item_ids_with_candidate_matches": len(matching_item_ids),
            "candidate_field_hashes": ranking,
            "evidence_warning": "Numeric equality (including u32 equals an item ID) is NOT a native semantic FK. Caller/schema proof is required. Original KIDS source byte SHA was audited upstream in M9; this import checks its declared counts and row consistency, not every original byte.",
        }
        db.commit()
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise ValueError("GRAPH_SQLITE_INTEGRITY_FAILURE:" + integrity)
        violations = db.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError("GRAPH_SQLITE_FOREIGN_KEY_FAILURE:" + str(violations[:3]))
    (out / "native_evidence_graph_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (out / "native_item_candidate_property_hashes.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ranking[0]) if ranking else
                           ["property_hash","raw_equalities","distinct_named_item_ids","source_files","evidence"])
        w.writeheader()
        w.writerows(ranking)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--table", type=Path, default=SOURCE)
    p.add_argument("--catalog", type=Path, default=CATALOG)
    p.add_argument("--property-dir", type=Path, default=FIELDS)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(build(a.table, a.catalog, a.property_dir, a.output),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
