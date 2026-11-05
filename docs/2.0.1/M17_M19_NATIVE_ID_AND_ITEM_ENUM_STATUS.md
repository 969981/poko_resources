# Pokopia 2.0.1 M17–M19: native Pokémon identity and item material enum evidence

Date: 2026-11-05. Branch: `2.0.1_unpack`. All inputs are original version 2.0.1 source bytes. This is a read-only reverse-engineering evidence checkpoint, **not** a declaration that native species IDs or material category names have been recovered.

## Primary source fingerprints

| Original input | SHA-256 |
|---|---|
| `2.0.1/exefs/main` (NSO0) | `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f` |
| `UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin` | `2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f` |
| `root_019167_50ae86ef.kidsobjdb` | `86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541` |
| `root_053829_e2e43333.kidsobjdb` | `98c7f56f54155d9016f26a6510cb63fb8b016798d986aa3189e5c35fe3c8c1bb` |

## Pokémon typed source-object → target-texture-object edges (M17/M19)

1. The source-qualified icon crosswalk contains **609 rows / 603 distinct native icon texture object IDs**; icon filenames and `icon_poke_XXXX` suffixes remain *candidate texture numbers*, not native Pokédex IDs.
2. M17 parsed **678/678 original KIDSOBJDB** files with no parse failures. It located **603 exact typed u32 properties** whose native value equals a known icon texture object ID. All property hashes are **`0x2856A1B3`**, and all matched nodes have native type **`0x79991E79`**. Of these, 602 edges are in `root_019167_50ae86ef.kidsobjdb` and 1 in `root_053829_e2e43333.kidsobjdb`.
3. M19 *independently parsed both source and target node records and checked original byte offsets* for the 603 matches. Every edge has **a distinct source OID and target OID**, and all 603 source OIDs are **absent from the 609-row known icon index**. All 603 source objects have **G1T resource hash = 0 and TEXINFO resource hash = 0**; their targets possess actual nonzero G1T/TEXINFO resource hashes. This is evidence of a native object-indirection relation, not a species key.
4. Example (physical original database): source OID `0x004027AC` at node byte offset `316`, property `0x2856A1B3` at byte offset `384` contains target OID `0x0E42969F`. Target node at offset `30124` carries G1T `0xF9C92DD0` and TEXINFO `0x309BD505`, resolving to `icon_poke_uni_0036_00_00_00`. `0036` is a filename component, not a proven native Pokémon species ID.
5. **`species_id_bindings_verified = 0`**. Source class and native property consumer must be proven before populating a species/forme identifier. The 6 duplicate-name texture sources must remain independently qualified by resource hashes.

Source outputs:
- `UnPack/2.0.1/Resources/Pokemon/NativeCallers/M17/m17_report.json`
- `UnPack/2.0.1/Resources/Pokemon/NativeCallers/M17/pokemon_typed_icon_oid_backrefs.csv`
- `UnPack/2.0.1/Resources/Pokemon/NativeCallers/M19/m19_texture_object_edge_summary.json`
- `UnPack/2.0.1/Resources/Pokemon/NativeCallers/M19/m19_verified_texture_object_edges.csv`

## Item native consumer callchain (M18)

Original `00983.bin` is `64-byte header + 4600 × 68-byte records`. `+0x22` is a native item name index verified by nine text tables. `+0x26`, `+0x39`, and `+0x3A` are observed byte offsets with **unproven in-game semantic naming**.

M18 disassembled eight anchored original ARM64 windows; overlap-deduplicated counts: **9 unique local LDR-vtable-slot/BLR patterns**, **10 unique local field byte reads**, and ten distinct direct `BL` destinations. Previous 17 / 26 counts included overlapping anchor windows and should not be cited as unique instruction sites.

### Native evidence: loop A

```asm
main+0xE5AA08  cmp  w8, #0xC7
main+0xE5AA20  ldr  x8, [x8,#0x38]
main+0xE5AA24  blr  x8
main+0xE5AA34  ldr  x8, [x8,#0x30]
main+0xE5AA38  blr  x8
main+0xE5AA58  ldr  x8, [x21,#8]
main+0xE5AA60  ldrb w0, [x8,#0x26]
main+0xE5AA64  sub  w8, w0, #1
main+0xE5AA68  cmp  w8, #0x13
main+0xE5AA6C  b.hi #0xE5A9E0
```

### Native evidence: loop B

```asm
main+0x10289DC  ldr  x8, [x8,#0x30]
main+0x10289E0  blr  x8
main+0x10289E8  ldr  x8, [x0,#8]
main+0x10289F4  ldrb w21, [x8,#0x26]
main+0x1028A00  cmp  w8, #0x13
main+0x1028A28  bl   #0xABBA30
main+0x1028A38  ldrb w8, [x8,#0x39]
```

### Native evidence: registry and group checks

```asm
main+0xABBB00  adrp x20, #0x3561000
main+0xABBB04  add  x20, x20, #0x8F0
main+0xABBB10  cmp  w9, #0xC7
main+0xABBB14  mov  w9, #0x638
main+0xABBB20  ldr  x0, [x8,#0x10]
main+0xABBB44  ldr  x8, [x8,#0x30]
main+0xABBB48  blr  x8
main+0xABBB50  ldr  x8, [x0,#8]
main+0xABBB64  ldrb w8, [x8,#0x3A]
main+0xABBB68  cmp  w8, #0xF
main+0xABBBD4  ldrb w8, [x8,#0x3A]
main+0xABBBD8  cmp  w8, #0x15
```

These prove local native **registry/index check → object virtual dispatch → returned object +8 → actual byte load → comparison**, but DO NOT prove that the backing object is a direct/unmodified `00983.bin` record or that `0xF` and `0x15` are source material enum labels. M17 direct `vtable+0x30` vs `ID*68` strict-window intersection yielded zero; the method may instead invoke helpers, use pointer tables, or return converted data.

Source outputs:
- `UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M18/m18_original_item_callgraph.json`
- `UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M18/m18_original_item_callgraph_summary.json`

## Required verification gates (not yet met)

**Species mapping:** recover an original species/variant or NPC/villager identity field and its runtime consumer, **plus** trace that field through an original object hash to a known G1T/TEXINFO target (with visual confirmation). First inspect the code consumer or recovered native RNK label for property `0x2856A1B3`, with the source zero-hash object explicitly considered. Do not promote the numerical portion of a texture name.

**Material enum:** identify the concrete class constructor registered at `0xC7` and real vtable object; find the dynamic destination of its `+0x30` virtual method, show its return object `+8` points into a table loaded from `00983.bin` or prove the transformation; then trace `+0x26/+0x3A` into a documented material-specific branch or table entry with enum names. A comparison against a literal is not a semantic classification.

**Runtime option:** existing `Scripts/resources/m15_gdb_verify_item983_runtime.py` supplies a non-patching, auto-resuming GDB probe for `+0xE5AA60` and `+0x10289F4`. It compares **all 68 bytes** for 3+ different IDs to the source table; read-only runtime logs are still required before a full native physical-record assertion. A matching single byte is insufficient.

## Reproduction

```bash
python -m Scripts.resources.m17_pokemon_object_backrefs
python -m Scripts.resources.m18_original_consumer_callgraph --self-test
python -m Scripts.resources.m18_original_consumer_callgraph
python -m Scripts.resources.m19_pokemon_texture_object_edges --self-test
python -m Scripts.resources.m19_pokemon_texture_object_edges
```

M18 requires `lz4>=4,<5` and `capstone>=5,<6`. GitHub Actions include sparse original-source checkout, hash checks, fail-closed tests, and committed CSV/JSON audits.

CI:
- `.github/workflows/unpack-m17-pokemon-oid-backrefs.yml`
- `.github/workflows/unpack-m18-original-item-callgraph.yml`
- `.github/workflows/unpack-m19-pokemon-texture-object-edges.yml`

**Acceptance:** `native_species_id_verified` stays blank, `species_id_bindings_verified=0`, `verified_material_type_enum=false`, and the classification remains a raw candidate until proof gates pass.
