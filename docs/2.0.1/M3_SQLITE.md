# Pokopia 2.0.1 — M3 evidence-linked SQLite catalogue

This indexes **already-published** resource records, not game binaries. It joins existing `m3_resource_type_index.csv`, original RDB/RDX/IDX offsets, `missing_input_records.csv`, and the eight verified KIDSOBJDB structural JSONL shards. No original binary files are added to the Git repository by this workflow.

## Inputs / validation

- 89,507 published resources with existing output paths and SHA-256 (M3 type index).
- 98,130 original IDX/RDB records, including empty LINKDATA entries and missing physical RDB sources.
- 6,118 records missing original physical containers, distinct from failures.
- 4,144 scanned KIDSOBJDB sources with per-record SHA-256, IDOK/RDOK blocks and bounded typed property samples.
- Strict mode fails on record count differences, missing ID joins, SHA discrepancies, invalid paths or block-count mismatches.

Original RDB/RDX and IDX records are re-read at build time; `source_locations` stores the source index path, record offset, original container path, file/entry offset, packed size and codec flags. When multiple files use a common source name, the exact `record_id` disambiguates them.

## Build

Run [M3 relational SQLite workflow](../../.github/workflows/unpack-m3-sqlite.yml) on `2.0.1_unpack` (automatically triggered by changes to the workflow / database parser). The workflow's **30-day Artifact** holds:

- `pokopia_2.0.1_m3_catalog.sqlite.gz`: relational SQLite database with indexes.
- `exports/resources.csv`, `source_locations.csv`, `missing_records.csv`.
- `exports/kidsobjdb_records.csv`, `kidsobjdb_fields.csv`, `hash_match_candidates.csv`.
- `exports/resources.jsonl.gz`, `summary.json`, sample lookup JSON.

Only a small summary (`UnPack/2.0.1/_reports/m3_sqlite_summary.json`) is persisted to Git, not a potentially huge SQLite database.

## Query examples

```powershell
# Extract .sqlite.gz first. Then query original source, offsets, fields and candidate matches.
python -m Scripts.unpack.m3_database lookup --db pokopia_2.0.1_m3_catalog.sqlite --record root:10349 --limit 25
python -m Scripts.unpack.m3_database lookup --db pokopia_2.0.1_m3_catalog.sqlite --hash 20a6a0bb --limit 20
```

SQLite SQL:

```sql
-- Which verified type-hash records are mapped to the same original container?
SELECT r.record_id, r.name_hash, r.native_extension_hint, r.evidence_grade,
       s.original_container_path, s.payload_offset, s.stored_bytes, r.decoded_sha256
FROM resources AS r JOIN source_locations AS s USING (record_id)
WHERE r.type_hash = '20a6a0bb'
LIMIT 50;

-- Find KIDSOBJDB property hashes and typed (sampled) values.
SELECT f.record_id, f.block_index, f.field_index, f.name_hash, f.type_code,
       f.value_count, f.sample_values_json
FROM kidsobjdb_fields AS f WHERE f.name_hash = 'a1b2c3d4' LIMIT 50;

-- *Unverified candidates only*. Never treat numeric/hash equality as a proven reference.
SELECT source_record_id, numeric_hex, target_record_id, evidence
FROM hash_match_candidates LIMIT 50;
```

## What this **does not** prove

KIDSOBJDB fields currently use *hash names*, not reliably decoded English/Chinese field names; the M4 parser retained only the first eight sampled values for each fixed-width field. `RDOK` word meaning and cross-resource references are not independently established. Any equal numeric `u32` value and record name hash is **UNVERIFIED_U32_VALUE_EQUALS_NAME_HASH** — a collision/candidate, not a confirmed link. M3 prefix survey found no independently confirmed BFBS schema; `MissionSettings` has not been proven to map to any particular source record and must be followed through PE factory metadata / Lua handle evidence before naming a resource.

No metadata completeness claim implies 100% semantic decoding or availability of the 27 missing physical files.
