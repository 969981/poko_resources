"""Build a provenance-first SQLite catalogue from verified M3/M4 reports.

No game binaries are fetched or transformed.  Block/field data is derived from
already-published, SHA-checked M4 KIDSOBJDB JSONL evidence.  Numeric/hash
collisions are *candidates* and must not be mistaken for proven references.

Usage:
    python -m Scripts.unpack.m3_database build --types m3_resource_type_index.csv \
        --m4-index m4_kidsobjdb_index.csv --m4-dir m4_kidsobjdb_data \
        --missing missing_input_records.csv --out m3_catalog.sqlite \
        --exports m3_exports --strict
    python -m Scripts.unpack.m3_database lookup --db m3_catalog.sqlite --hash 20a6a0bb
    python -m Scripts.unpack.m3_database lookup --db m3_catalog.sqlite --record root:10349
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath

from .core import parse_idx, parse_rdb, parse_rdx

EXPECTED_TYPES = 89507
EXPECTED_KIDSOBJDB = 4144
EXPECTED_MISSING = 6118
SCHEMA_VERSION = 1
ID_RE = re.compile(r'^(?:root|system|link):\d+$')
HEX8_RE = re.compile(r'^[0-9a-f]{8}$')

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE resources (
 record_id TEXT PRIMARY KEY, catalog TEXT NOT NULL,
 record_index INTEGER NOT NULL, source_path TEXT NOT NULL,
 output_path TEXT NOT NULL, decoded_sha256 TEXT NOT NULL,
 name_hash TEXT, type_hash TEXT, unpacked_size INTEGER NOT NULL,
 native_extension_hint TEXT, evidence_grade TEXT NOT NULL,
 signature TEXT NOT NULL, head_64_hex TEXT NOT NULL,
 probe_status TEXT NOT NULL,
 UNIQUE(catalog, record_index)
);
CREATE TABLE missing_records (
 record_id TEXT PRIMARY KEY, catalog TEXT NOT NULL,
 record_index INTEGER NOT NULL, source_file TEXT NOT NULL,
 name_hash TEXT, type_hash TEXT, unpacked_size INTEGER NOT NULL,
 platform_flags TEXT NOT NULL, reason TEXT NOT NULL
);
CREATE TABLE kidsobjdb_records (
 record_id TEXT PRIMARY KEY REFERENCES resources(record_id),
 semantic_status TEXT NOT NULL, bytes INTEGER NOT NULL,
 sha256 TEXT NOT NULL, block_count INTEGER NOT NULL,
 idok_blocks INTEGER NOT NULL, rdok_blocks INTEGER NOT NULL,
 partial_blocks INTEGER NOT NULL, warnings_json TEXT NOT NULL
);
CREATE TABLE kidsobjdb_blocks (
 record_id TEXT NOT NULL REFERENCES kidsobjdb_records(record_id),
 block_index INTEGER NOT NULL, kind TEXT NOT NULL,
 offset INTEGER NOT NULL, size INTEGER NOT NULL, block_sha256 TEXT NOT NULL,
 name_hash TEXT, type_hash TEXT, property_count INTEGER NOT NULL,
 parse_status TEXT NOT NULL, raw_u32_json TEXT,
 PRIMARY KEY (record_id, block_index)
);
CREATE TABLE kidsobjdb_fields (
 record_id TEXT NOT NULL, block_index INTEGER NOT NULL,
 field_index INTEGER NOT NULL, name_hash TEXT NOT NULL,
 type_code INTEGER NOT NULL, value_count INTEGER NOT NULL,
 value_bytes INTEGER, parse_status TEXT NOT NULL,
 sample_values_json TEXT NOT NULL,
 PRIMARY KEY(record_id, block_index, field_index),
 FOREIGN KEY(record_id,block_index) REFERENCES kidsobjdb_blocks(record_id,block_index)
);
-- Hash-equal numeric samples are NOT independently verified object references.
CREATE TABLE hash_match_candidates (
 source_record_id TEXT NOT NULL, block_index INTEGER NOT NULL,
 field_index INTEGER NOT NULL, sample_index INTEGER NOT NULL,
 numeric_hex TEXT NOT NULL, target_record_id TEXT NOT NULL,
 evidence TEXT NOT NULL CHECK(evidence='UNVERIFIED_U32_VALUE_EQUALS_NAME_HASH'),
 PRIMARY KEY(source_record_id,block_index,field_index,sample_index,target_record_id),
 FOREIGN KEY(target_record_id) REFERENCES resources(record_id)
);
CREATE TABLE source_locations (
 record_id TEXT PRIMARY KEY, catalog TEXT NOT NULL,
 original_index_path TEXT NOT NULL, index_record_offset INTEGER NOT NULL,
 original_container_path TEXT NOT NULL, payload_offset INTEGER NOT NULL,
 stored_bytes INTEGER NOT NULL, unpacked_bytes INTEGER NOT NULL,
 codec_flags TEXT NOT NULL, footer_layout TEXT,
 source_present_in_repo INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE audit(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def csv_rows(path: Path):
    with Path(path).open('r', encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def nonnegative_int(value, label: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError) as e:
        raise ValueError(f'INVALID_INTEGER:{label}:{value}') from e
    if n < 0:
        raise ValueError(f'NEGATIVE_INTEGER:{label}:{value}')
    return n


def hash_value(value: str | None):
    value = (value or '').strip().lower().removeprefix('0x')
    if not value:
        return None
    if not HEX8_RE.fullmatch(value):
        raise ValueError('INVALID_HASH:' + value)
    return value


def record_key(value: str):
    if not ID_RE.fullmatch(value or ''):
        raise ValueError('INVALID_RECORD_ID:' + str(value))
    return value


def relative_asset_path(raw: str):
    # These are published Git paths relative to UnPack/2.0.1.
    paths = [p for p in raw.split(';') if p]
    if not paths:
        raise ValueError('MISSING_OUTPUT_PATH')
    for p in paths:
        parts = PurePosixPath(p)
        if parts.is_absolute() or '..' in parts.parts or parts.parts[0] != 'romfs':
            raise ValueError('UNSAFE_ASSET_PATH:' + p)
    return raw


def insert_resources(db: sqlite3.Connection, source: Path):
    n, kinds = 0, Counter()
    query = '''INSERT INTO resources
      (record_id,catalog,record_index,source_path,output_path,decoded_sha256,
       name_hash,type_hash,unpacked_size,native_extension_hint,evidence_grade,
       signature,head_64_hex,probe_status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)'''
    for row in csv_rows(source):
        rid = record_key(row['record_id'])
        catalog, idx = rid.split(':', 1)
        sha = row['output_sha256'].strip().lower()
        if not re.fullmatch(r'[0-9a-f]{64}', sha):
            raise ValueError('INVALID_OUTPUT_SHA:' + rid)
        db.execute(query, (rid, catalog, int(idx), row['source_path'],
                           relative_asset_path(row['output_path']), sha,
                           hash_value(row.get('name_hash')), hash_value(row.get('type_hash')),
                           nonnegative_int(row['unpacked_size'], 'unpacked_size'),
                           row.get('native_extension_hint', ''), row.get('evidence_grade', ''),
                           row.get('signature', ''), row.get('head_64_hex', ''),
                           row.get('m3_probe_status', '')))
        kinds[catalog] += 1
        n += 1
    return n, kinds


def insert_source_locations(db, indexes_base: Path | None, link_idx: Path | None,
                            *, strict: bool = False):
    if strict and (indexes_base is None or link_idx is None):
        raise ValueError('ORIGINAL_INDEX_SOURCES_REQUIRED_FOR_STRICT_PROVENANCE')
    count = 0
    query = '''INSERT INTO source_locations
      (record_id,catalog,original_index_path,index_record_offset,original_container_path,
       payload_offset,stored_bytes,unpacked_bytes,codec_flags,footer_layout,source_present_in_repo)
       VALUES(?,?,?,?,?,?,?,?,?,?,?)'''
    if indexes_base is not None:
        base = Path(indexes_base)
        for catalog in ('root', 'system'):
            rdx = parse_rdx((base / f'{catalog}.rdx').read_bytes())
            records, _ = parse_rdb((base / f'{catalog}.rdb').read_bytes(), catalog, rdx)
            for e in records:
                rid = f'{catalog}:{e.record_index}'
                if e.footer_magic == 0x0c01:
                    source = (base / 'data' / f'0x{e.name_hash:08x}.file').as_posix()
                    location_status = 'STANDALONE_FILE'
                else:
                    rd = rdx[e.fdata_index] if e.fdata_index >= 0 else None
                    roots = {0xffff: base, 0xff01: base / 'MountPoint_1',
                             0xff02: base / 'MountPoint_2'}
                    source = ((roots.get(rd.platform_flags, base) / rd.filename).as_posix()
                              if rd is not None else '')
                    location_status = e.footer_layout
                db.execute(query, (rid, catalog, (base / f'{catalog}.rdb').as_posix(),
                                   e.rdb_offset, source, e.fdata_offset, e.fdata_entry_size,
                                   e.uncompressed_size, f'0x{e.flags:08x}', location_status, 0))
                count += 1
    if link_idx is not None:
        idx = Path(link_idx)
        for e in parse_idx(idx.read_bytes()):
            db.execute(query, (f'link:{e.index}', 'link', idx.as_posix(), e.index * 32,
                               (idx.parent / 'LD_C0_R.BIN').as_posix(), e.offset,
                               e.stored_size, e.unpacked_size, str(e.flag), 'INDEX_32_BYTES', 0))
            count += 1
    db.execute('''UPDATE source_locations SET source_present_in_repo=1
                  WHERE record_id IN (SELECT record_id FROM resources)''')
    if strict:
        unpublished = db.execute('''SELECT COUNT(*) FROM resources r LEFT JOIN source_locations s
                                    ON r.record_id=s.record_id WHERE s.record_id IS NULL''').fetchone()[0]
        if unpublished:
            raise ValueError(f'PUBLISHED_RESOURCE_WITHOUT_SOURCE_LOCATOR:{unpublished}')
        missing = db.execute('''SELECT COUNT(*) FROM missing_records r LEFT JOIN source_locations s
                                ON r.record_id=s.record_id WHERE s.record_id IS NULL''').fetchone()[0]
        if missing:
            raise ValueError(f'MISSING_RESOURCE_WITHOUT_SOURCE_LOCATOR:{missing}')
        mismatch = db.execute('''SELECT COUNT(*) FROM resources r JOIN source_locations s
                                 ON r.record_id=s.record_id WHERE r.unpacked_size<>s.unpacked_bytes''').fetchone()[0]
        if mismatch:
            raise ValueError(f'INDEX_UNPACKED_SIZE_MISMATCH:{mismatch}')
    return count


def insert_missing(db: sqlite3.Connection, source: Path):
    count = 0
    query = '''INSERT INTO missing_records
        (record_id,catalog,record_index,source_file,name_hash,type_hash,
        unpacked_size,platform_flags,reason) VALUES(?,?,?,?,?,?,?,?,?)'''
    for row in csv_rows(source):
        rid = record_key(row['record_id'])
        catalog, idx = rid.split(':', 1)
        db.execute(query, (rid, catalog, int(idx), row['source_file'],
                           hash_value(row.get('name_hash')),hash_value(row.get('type_hash')),
                           nonnegative_int(row['unpacked_size'], 'missing_size'),
                           row.get('platform_flags', ''), row.get('reason', '')))
        count += 1
    return count


def load_kids_index(source: Path):
    records = {}
    for row in csv_rows(source):
        rid = record_key(row['record_id'])
        if rid in records:
            raise ValueError('DUPLICATE_M4_INDEX_RECORD:' + rid)
        records[rid] = row
    return records


def insert_structured(db, shard_dir: Path, index: dict, *, source_shards=8):
    paths = sorted(Path(shard_dir).glob('m4_shard*.jsonl.gz'))
    if len(paths) != source_shards:
        raise ValueError(f'M4_SHARD_COUNT_MISMATCH:{len(paths)}:{source_shards}')
    seen, counts = set(), Counter()
    for path in paths:
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                if not line.strip():
                    continue
                data = json.loads(line)
                rid = record_key(data['record_id'])
                if rid in seen:
                    raise ValueError('DUPLICATE_M4_JSONL_RECORD:' + rid)
                seen.add(rid)
                meta = index.get(rid)
                if not meta or data['status'] != meta['status']:
                    raise ValueError('M4_INDEX_JSONL_MISMATCH:' + rid)
                if data['status'] == 'PARSE_FAILED':
                    raise ValueError('M4_SOURCE_PARSE_FAILED:' + rid)
                parsed = data.get('decoded')
                if not parsed or parsed['magic'] != '_DOK0000':
                    raise ValueError('M4_MISSING_DECODED_STRUCT:' + rid)
                orig = db.execute('SELECT decoded_sha256,unpacked_size,source_path FROM resources WHERE record_id=?',
                                  (rid,)).fetchone()
                if not orig:
                    raise ValueError('M4_RECORD_NOT_IN_M3_CATALOG:' + rid)
                size = nonnegative_int(parsed['bytes'], 'kidsobjdb_bytes')
                if parsed['sha256'].lower() != orig[0] or size != orig[1] or data['source_path'] != orig[2]:
                    raise ValueError('M4_INPUT_PROVENANCE_MISMATCH:' + rid)
                if len(parsed['blocks']) != parsed['header']['entry_count']:
                    raise ValueError('M4_BLOCK_COUNT_MISMATCH:' + rid)
                summary = parsed['summary']
                db.execute('''INSERT INTO kidsobjdb_records VALUES(?,?,?,?,?,?,?, ?,?)''',
                           (rid, data['status'],size,parsed['sha256'].lower(),len(parsed['blocks']),
                            summary['IDOK'],summary['RDOK'],summary['PARTIAL_BLOCKS'],
                            json.dumps(parsed['warnings'],ensure_ascii=False)))
                counts['kids_records'] += 1
                for block in parsed['blocks']:
                    bidx = nonnegative_int(block['index'], 'block_index')
                    db.execute('''INSERT INTO kidsobjdb_blocks
                      (record_id,block_index,kind,offset,size,block_sha256,name_hash,type_hash,
                       property_count,parse_status,raw_u32_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                      (rid,bidx,block['kind'],nonnegative_int(block['offset'],'block_offset'),
                       nonnegative_int(block['size'],'block_size'),block['sha256'].lower(),
                       hash_value(block.get('name_hash')),hash_value(block.get('type_hash')),
                       nonnegative_int(block.get('property_count',0), 'property_count'),
                       block['status'],json.dumps(block.get('raw_u32_hex'),ensure_ascii=False)))
                    counts['blocks'] += 1
                    for field in block.get('properties',[]):
                        fidx = nonnegative_int(field['index'],'field_index')
                        samples = field.get('sample_values',[])
                        db.execute('''INSERT INTO kidsobjdb_fields
                          (record_id,block_index,field_index,name_hash,type_code,value_count,
                           value_bytes,parse_status,sample_values_json) VALUES(?,?,?,?,?,?,?,?,?)''',
                          (rid,bidx,fidx,hash_value(field['name_hash']),
                           nonnegative_int(field['type_code'],'field_type'),
                           nonnegative_int(field['count'],'field_count'),
                           field.get('value_bytes'),field['status'],
                           json.dumps(samples,ensure_ascii=False,separators=(',',':'))))
                        counts['fields'] += 1
                        # Candidate relation is a *numeric collision*, not a proven pointer.
                        if field['type_code'] == 5:
                            for i, value in enumerate(samples):
                                if isinstance(value,int) and 0 <= value <= 0xffffffff:
                                    target_hash = f'{value:08x}'
                                    # Lookup is index-backed, indexes built in load phase.
                                    for (target,) in db.execute('SELECT record_id FROM resources WHERE name_hash=?', (target_hash,)):
                                        db.execute('''INSERT OR IGNORE INTO hash_match_candidates
                                         (source_record_id,block_index,field_index,sample_index,numeric_hex,target_record_id,evidence)
                                         VALUES(?,?,?,?,?,?,?)''',
                                         (rid,bidx,fidx,i,target_hash,target,
                                          'UNVERIFIED_U32_VALUE_EQUALS_NAME_HASH'))
                                        counts['unverified_hash_matches'] += 1
    if seen != set(index):
        raise ValueError(f'M4_SHARD_INDEX_COVERAGE_MISMATCH:{len(seen)}:{len(index)}')
    return counts


def export_table(db, table, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    cur = db.execute('SELECT * FROM ' + table)
    columns = [x[0] for x in cur.description]
    with path.open('w',encoding='utf-8',newline='') as f:
        writer = csv.writer(f); writer.writerow(columns)
        for row in cur:
            writer.writerow(row)


def build(types: Path, m4_index: Path, m4_dir: Path, missing: Path, out: Path,
          exports: Path, strict: bool = False, expected_types: int = EXPECTED_TYPES,
          expected_m4: int = EXPECTED_KIDSOBJDB, expected_missing: int = EXPECTED_MISSING,
          indexes_base: Path | None = None, link_idx: Path | None = None):
    out, exports = Path(out),Path(exports)
    out.parent.mkdir(parents=True,exist_ok=True)
    exports.mkdir(parents=True,exist_ok=True)
    # Build in a disposable temporary file; an interrupted run never publishes a partial DB.
    with tempfile.NamedTemporaryFile(prefix='.m3_catalog_',suffix='.sqlite',dir=out.parent,delete=False) as f:
        temporary = Path(f.name)
    db = None
    try:
        db = sqlite3.connect(temporary)
        db.execute('PRAGMA journal_mode=DELETE')
        db.execute('PRAGMA synchronous=OFF')
        db.execute('PRAGMA cache_size=-32768')
        db.executescript(SCHEMA)
        with db:
            n, kinds = insert_resources(db,types)
            m = insert_missing(db,missing)
            locations = insert_source_locations(db, indexes_base, link_idx, strict=strict)
            index = load_kids_index(m4_index)
            if strict and (n != expected_types or len(index) != expected_m4 or m != expected_missing):
                raise ValueError(f'M3_EXPECTED_COUNTS_MISMATCH:{n}:{len(index)}:{m}')
            db.execute('CREATE INDEX resources_by_name_hash ON resources(name_hash)')
            db.execute('CREATE INDEX resources_by_type_hash ON resources(type_hash)')
            db.execute('CREATE INDEX resources_by_source ON resources(source_path)')
            result=insert_structured(db,m4_dir,index)
            db.execute('CREATE INDEX fields_by_name_hash ON kidsobjdb_fields(name_hash)')
            db.execute('CREATE INDEX blocks_by_name_hash ON kidsobjdb_blocks(name_hash)')
            db.execute('CREATE INDEX candidates_by_target ON hash_match_candidates(target_record_id)')
            db.execute('CREATE INDEX missing_by_source ON missing_records(source_file)')
            db.execute('CREATE INDEX locations_by_container ON source_locations(original_container_path)')
            summary={'m3_resources':n, 'm3_by_catalog':dict(kinds),'missing_input_records':m,
                     'original_index_records':locations,
                     'm4_kidsobjdb_records':result['kids_records'],
                     'm4_blocks':result['blocks'], 'm4_fields':result['fields'],
                     'unverified_numeric_hash_matches':result['unverified_hash_matches'],
                     'bfbs_schema_names_verified':0,
                     'semantic_complete':False,'source': 'M3 type-index + M4 sampled KIDSOBJDB evidence',
                     'limitations':[
                       'Only bounded numeric samples from M4 are indexed; not all original field values.',
                       'RDOK words and unknown schemas are not semantic links.',
                       'U32 equality with a name hash is only an unverified candidate.',
                       'Real asset names and MissionSettings mapping require independent evidence.',
                       'No BFBS signature was confirmed by the published M3 prefix survey.'
                     ]}
            for key,value in summary.items():
                db.execute('INSERT INTO audit(key,value) VALUES(?,?)',(key,json.dumps(value,ensure_ascii=False)))
            db.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
        # Explicit SQL integrity and referential checks.
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLITE_INTEGRITY_CHECK_FAILED')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLITE_FOREIGN_KEY_CHECK_FAILED')
        export_table(db,'resources',exports/'resources.csv')
        export_table(db,'missing_records',exports/'missing_records.csv')
        export_table(db,'source_locations',exports/'source_locations.csv')
        export_table(db,'kidsobjdb_records',exports/'kidsobjdb_records.csv')
        export_table(db,'kidsobjdb_fields',exports/'kidsobjdb_fields.csv')
        export_table(db,'hash_match_candidates',exports/'hash_match_candidates.csv')
        # JSONL contains every type-indexed resource without re-dumping binary assets.
        with gzip.open(exports/'resources.jsonl.gz','wt',encoding='utf-8',compresslevel=6) as f:
            cur=db.execute('SELECT * FROM resources ORDER BY catalog,record_index')
            labels=[c[0] for c in cur.description]
            for values in cur:
                f.write(json.dumps(dict(zip(labels,values)),ensure_ascii=False,separators=(',',':'))+'\n')
        (exports/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        db.close();db=None
        os.replace(temporary,out)
        return summary
    finally:
        if db is not None:
            db.close()
        temporary.unlink(missing_ok=True)


def lookup(database: Path, record: str|None, hash_text: str|None, limit: int):
    if not (record or hash_text):
        raise ValueError('LOOKUP_REQUIRES_RECORD_OR_HASH')
    if limit<1 or limit>10000:
        raise ValueError('LOOKUP_LIMIT_OUT_OF_RANGE')
    with sqlite3.connect(f'file:{Path(database).resolve().as_posix()}?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        if record:
            record_key(record)
            resources=[dict(r) for r in db.execute('SELECT * FROM resources WHERE record_id=?',(record,))]
            source=[dict(r) for r in db.execute('SELECT * FROM source_locations WHERE record_id=?',(record,))]
            blocks=[dict(r) for r in db.execute('SELECT * FROM kidsobjdb_blocks WHERE record_id=? LIMIT ?', (record,limit))]
            fields=[dict(r) for r in db.execute('SELECT * FROM kidsobjdb_fields WHERE record_id=? LIMIT ?', (record,limit))]
            candidate=[dict(r) for r in db.execute('SELECT * FROM hash_match_candidates WHERE source_record_id=? LIMIT ?',(record,limit))]
            return {'resources':resources,'source_locations':source,'kidsobjdb_blocks':blocks,'kidsobjdb_fields':fields,
                    'unverified_hash_matches':candidate}
        h=hash_value(hash_text)
        return {'resources':[dict(r) for r in db.execute(
                 'SELECT * FROM resources WHERE name_hash=? OR type_hash=? LIMIT ?',(h,h,limit))],
                'kidsobjdb_fields':[dict(r) for r in db.execute(
                 'SELECT * FROM kidsobjdb_fields WHERE name_hash=? LIMIT ?',(h,limit))],
                'missing_input_records':[dict(r) for r in db.execute(
                 'SELECT * FROM missing_records WHERE name_hash=? OR type_hash=? LIMIT ?',(h,h,limit))]}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    b=sub.add_parser('build')
    b.add_argument('--types',type=Path,required=True)
    b.add_argument('--m4-index',type=Path,required=True)
    b.add_argument('--m4-dir',type=Path,required=True)
    b.add_argument('--missing',type=Path,required=True)
    b.add_argument('--out',type=Path,required=True)
    b.add_argument('--exports',type=Path,required=True)
    b.add_argument('--strict',action='store_true')
    b.add_argument('--indexes-base',type=Path)
    b.add_argument('--link-idx',type=Path)
    b.add_argument('--expected-types',type=int,default=EXPECTED_TYPES)
    b.add_argument('--expected-m4',type=int,default=EXPECTED_KIDSOBJDB)
    b.add_argument('--expected-missing',type=int,default=EXPECTED_MISSING)
    l=sub.add_parser('lookup')
    l.add_argument('--db',required=True,type=Path)
    l.add_argument('--record')
    l.add_argument('--hash')
    l.add_argument('--limit',type=int,default=25)
    a=p.parse_args(argv)
    if a.command=='build':
        print(json.dumps(build(a.types,a.m4_index,a.m4_dir,a.missing,a.out,a.exports,a.strict,
                               a.expected_types,a.expected_m4,a.expected_missing,
                               a.indexes_base,a.link_idx),ensure_ascii=False,indent=2))
    else:
        print(json.dumps(lookup(a.db,a.record,a.hash,a.limit),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
