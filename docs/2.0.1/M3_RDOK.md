# M3 next stage: RDOK hash crosswalk and ExeFS static strings

Run `python -m Scripts.unpack.m3_rdok_crosswalk --types m3_resource_type_index.csv --shards m4_kidsobjdb_data --out output --exefs 2.0.1/exefs/main`.

This workflow uses the original SHA-verified M4 structure-scan data. It compares all 40 known RDOK 32-bit word quartets against **three independently indexed domains**: RDB resource name hashes, parsed IDOK block name hashes and KIDSOBJDB document header hashes. A hit is only *numeric equality*, NOT a proven runtime pointer. Results are stored in `m3_rdok_crosswalk.csv`; a field-hash/type frequency table is saved as an Actions artifact.

The ExeFS string scan searches exact UTF-8 and UTF-16LE literal occurrences of `MissionSettings`, `MissionInfo_array.bfbs`, `pe_FlatbuffersDataComponent`, `FlatBuffers` and `MissionInfo_array`. It records byte offsets and whole-file SHA-256, but no source-record identity inference. A literal string occurrence **does not** prove FlatBuffers schema files are accessible or establish a PE factory / Lua-handle relationship.

All 4,144 KIDSOBJDB metadata inputs must pass original decoded SHA-256 joins. The workflow fails on partial shard coverage, malformed hashes or changed block totals. Open the GitHub Actions artifact for `field_hash_frequency.csv`, the small summary and RDOK crosswalk in the branch under `UnPack/2.0.1/_reports/`.

Follow-up requires independent named asset metadata / an observed factory call chain to upgrade any candidate links to verified.

## Semantic cross-check and non-Pokopia negative control

The separate [DWOriginsAssetTool decoder](https://github.com/PieceMetal/DWOriginsAssetTool/blob/main/Core/KidsObjectDatabase.cs) treats RDOK as an inherited/reference layout with `object_hash,parent_database_hash,parent_object_hash,property_count`. Our 40 Pokopia word quartets fit that shape and have **40 unique KIDSOBJDB resource name-hash matches**, which is stronger than a blind collision survey. However, semantic promotion still requires target loader/consumer evidence.

The specific `MissionSettings_array.bfbs` and `MissionInfo_array.bfbs` paths are [Gen9 Scarlet/Violet data used by pkNX](https://github.com/kwsch/pkNX/blob/master/pkNX.WinForms/Dumping/Gen9/GameDumperSV.cs), **not known Pokopia resources**. ExeFS searches for these labels are cross-game negative controls and must not generate Pokopia filenames or database joins.
