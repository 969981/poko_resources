# M3 RDOK ↔ KIDSOBJDB verified-name-hash crosswalk

**Scope:** 15 SHA-256 verified diagnostic KIDSOBJDB resource records, which contain all 40 RDOK blocks known from the 4,144-record M4 survey. Every RDOK has a 28-byte `RDOK0000` block holding three equal little-endian u32 values followed by zero.

**Validation:** Join every observed 32-bit RDOK value against the `name_hash` field of all **4,144** KIDSOBJDB resource rows. Require source SHA-256 equality with the M4 index, exactly one target resource, and at least one IDOK block on the target.

**Measured:** 40/40 exact matches, 40 distinct targets, 40/40 same root/system catalog, 32 same FDATA, 8 cross-FDATA, zero ambiguous or missing matches. Example: `root:13184` (RDOK `55235e67`) → `root:20245`; `root:53394` contains eight distinct cross-FDATA candidates.

This is **strong static evidence for a reference-list encoding**, not proof that the game dereferences RDOK as a pointer, and not recovery of the true names. No BFBS/MissionSettings linkage is claimed.

Evidence: [m3_rdok_verified_40.csv](../../UnPack/2.0.1/_reports/m3_rdok_verified_40.csv) (40 per-record provenance rows), [m3_rdok_verified_40_summary.json](../../UnPack/2.0.1/_reports/m3_rdok_verified_40_summary.json), [original M4 diagnostics](../../UnPack/2.0.1/_reports/m4_unresolved_layout_diagnostics.json).

Next: independently inspect the KIDSOBJDB loader or RDOK consumer call path; only then promote hash-equality candidates into verified runtime relationships.

## Cross-game KIDS RDOK layout corroboration (not a Pokopia runtime trace)

The independently published [DWOriginsAssetTool KIDS reader](https://github.com/PieceMetal/DWOriginsAssetTool/blob/main/Core/KidsObjectDatabase.cs) parses the 16 bytes after `RDOK0000` + size as follows:

| Relative block offset | Hypothesized field | Pokopia observation |
| --- | --- | --- |
| +0x0C | `object_hash` | 32-bit candidate target hash |
| +0x10 | `parent_database_hash` | equals object_hash in all 40 |
| +0x14 | `parent_object_hash` | equals object_hash in all 40 |
| +0x18 | `property_count` | zero in all 40 |

In that independently observed game, RDOK is an inherited/reference record. The three equal hashes in Pokopia independently match 40 distinct KIDSOBJDB target records, all containing IDOK blocks. This is **strong cross-game static corroboration**, not proof that Pokopia resolves the reference via exactly the same runtime code.

## Scope correction: MissionSettings is not a Pokopia baseline

`world/data/club/MissionInfo/MissionInfo_array.bfbs` and `world/data/club/MissionSettings/MissionSettings_array.bfbs` are documented as **Pokémon Scarlet/Violet (Gen 9)** resources in [pkNX's Gen9 GameDumperSV](https://github.com/kwsch/pkNX/blob/master/pkNX.WinForms/Dumping/Gen9/GameDumperSV.cs). They were carried into an earlier Pokopia-oriented research plan from a separate SV investigation. Searching for those names in Pokopia ExeFS may be used as a **negative control** only; no evidence makes them genuine Pokopia resource identities. Future Pokopia schema work must discover native paths and identifiers independently.
