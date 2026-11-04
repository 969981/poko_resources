# Add 40 source-verified RDOK candidate edges to M3 SQLite

Existing database: from [M3 SQLite output](M3_SQLITE.md). Import source: `UnPack/2.0.1/_reports/m3_rdok_verified_40.csv`.

Default is read-only strict audit:

```powershell
python -m Scripts.unpack.m3_rdok_sqlite --db pokopia_2.0.1_m3_catalog.sqlite --crosswalk UnPack/2.0.1/_reports/m3_rdok_verified_40.csv
```

Only after the check passes, use `--apply` to create a table of **candidate relationships**, with foreign keys referencing 40 actual source/target rows. The importer verifies both decoded SHA-256 values against the original SQLite, exact RDOK block words, target KIDSOBJDB IDOK presence, resource name Hash, root/system catalog, source and target original FDATA paths. It is idempotent and refuses conflicting rows.

```sql
SELECT source_record_id, block_index, target_record_id, name_hash, same_container
FROM rdok_reference_candidates;
```

Important: These 40 rows are exact, source-backed *hash equality candidates*. The table sets `evidence='HASH_EQUALITY_ONLY_NOT_PROVEN_POINTER'`. This does **not** establish how the runtime resolves the RDOK data. Source/game binary files remain unchanged.
