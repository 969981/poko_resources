# Pokopia v2.0.1 native-suffix reconstruction

The versioned `UnPack/2.0.1/romfs/.../<original-source-filename>/decoded` records and `_manifest.csv` remain untouched.

The M3 index links each published record to native type hashes, validated magic and actual output part paths. The tool reconstructs a game-native file from one or more saved parts in order, SHA-256 checks the reassembled bytes and writes atomically outside the Git tree.

## Windows usage (local full/sparse checkout with selected blobs)

```powershell
python -m Scripts.unpack.export_native --index UnPack/2.0.1/_reports/m3_resource_type_index.csv --assets-root UnPack/2.0.1 --out E:/Test/Pokopia-Native --extensions g1m,g1t,kidsobjdb --allow-inferred
```

- Default exports only files whose extension is backed by actual magic; `--allow-inferred` enables external KT type-hash mappings, labelled as **inferences**, not proven converters.
- Use `--record-id root:10349 --extensions kidsobjdb` to reconstruct a proven 96-byte native record.
- Use `--limit 100` for limited batches or `--dry-run` to produce a preflight report.
- Already-correct exported files are verified before being reused; mismatched existing files cause an error.
- Missing Git blobs (e.g. partial/sparse clone) trigger explicit errors; they are never fabricated.
- Source assets larger than 2 GiB per record must be handled in smaller verified batches or with an explicit larger guard.
- Producing the native `.g1m`, `.g1t`, `.kidsobjdb` file is **not** the same as rendering/decoding into glTF/PNG/JSON.
