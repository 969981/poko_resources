# Pokopia 2.0.1 — M20 native Pokémon-property and item query evidence

> 2026-11-05; branch `2.0.1_unpack`. This document describes the **M20 native Pokémon property / item-lookup track**, not the separately documented M20 OpenSSL `NID=983` investigation in `M20_ITEM983_CACHE_ORIGIN.md`. The latter has **no proven relation** to LINKDATA `00983.bin`.

## Source identity and proof policy

- Original `2.0.1/exefs/main` SHA-256: `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`.
- Original `00983.bin` SHA-256: `2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`, with 64-byte header and `4600 × 68` original records.
- Typed KIDSOBJDB source-object to target-texture-object corpus: **603 original byte-checked M19 edges**; `native_species_id_verified` remains blank.
- Static hash literals, executable addresses, virtual function pointer neighborhoods and file offset histograms are **not by themselves** proof of a game's species ID, material enum names, storage limit or object class.

## M20: exact native hash literal and original item wrapper reverse graph

The property `0x2856A1B3` has one original aligned literal cell in NSO rodata at `main+0x2830C98`. The initial strictly bounded search found no direct adjacent MOVZ/MOVK or **exact-cell** ADRP/LDR references. **That negative observation was not proof of no consumer**: M20.1 expanded the search to adjacent table bases.

A full original AArch64 `BL` scan found **17 direct calls** to `main+0x2F1F0`, the already proven two-stage item query wrapper; no direct unconditional `B` to that exact address was found.

| Query stage | Original native instruction | Interpretation |
|---|---|---|
| Registry entry | `main+0x2F210` and `+0x2F220` | Bounds check for index `0xC7`; load first object |
| V1 interface | `main+0x2F234` / `+0x2F238` | `vtable+0x38` indirect call |
| V2 interface | `main+0x2F244` / `+0x2F24C` / `+0x2F258` | Forward item ID and tail-call `vtable+0x30` |
| Actual caller reads | 12/17 sampled bounded call windows contain `ldr x?, [x0,#8]` | Direct observation of wrapper-return pointer access; exact pointer origin still unknown |

Follow-on reads at individual callers include `+0x0C`, `+0x14`, `+0x18`, `+0x1E`, `+0x27`, `+0x3A`, and `+0x41`. Some callers do not dereference the query result within their bounded window. The CSV preserves precise caller PC, field instruction and original ExeFS hash. **Do not combine unrelated pointers solely because their offsets match `00983.bin`.**

The native `00983.bin` raw-byte frequency checks (e.g. `+0x26`: 15 distinct values; `+0x3A`: 16 distinct values) are statistical controls only; the queried memory has not been proven to originate from these file records.

## M20.1/M20.2: native three-property array and real indexed consumer

Original NSO rodata has this contiguous array:

| RVA | Original little-endian u32 | Evidence |
|---|---|---|
| `0x2830C90` | `0xC8BB66DA` | G1T resource-property hash |
| `0x2830C94` | `0x2276FC56` | TEXINFO resource-property hash |
| `0x2830C98` | `0x2856A1B3` | Third KIDSOBJDB property hash, **native semantic name unproven** |

The following exact original AArch64 data path is verified:

```asm
main+0xCE8554  cmp  w3, #2
main+0xCE8558  b.hi #0xCE8598
main+0xCE855C  adrp x8, #0x2830000
main+0xCE8560  add  x8, x8, #0xC90
main+0xCE8564  adrp x9, #0x3330000
main+0xCE8568  add  x9, x9, #0x928
main+0xCE856C  ldr  w11, [x8, w3, sxtw #2]
main+0xCE8570  ldr  x12, [x9, w3, sxtw #3]
main+0xCE8574  mov  w10, #1
main+0xCE8578  movk w10, #0x500, lsl #16
main+0xCE857C  stp  w10, w11, [x1]
main+0xCE8588  stp  x12, x11, [x1, #8]
```

This establishes an original **three-entry, index-selected property-hash load and descriptor-shaped output write**. The parallel pointer array is located at `main+0x3330928` in data. A native property **hash consumer** is now identified in the *descriptor construction* sense. The property label, object type identity and whether the downstream object is a Pokémon species/form record remain open. Do not set `species_id_bindings_verified` above zero.

M20.1 found 28 ADRP page matches, 9 adjacent native addresses within ±0x100 of the unknown-property hash, and no direct raw 64-bit pointer to the hash literal vicinity. These are separate from the proved `0xCE856C` **indexed** hash read.

## M20.3: function-pointer backreferences (corrected null-pointer classifier)

The native function at `main+0xCE854C` has **zero direct BL and zero direct B callers** in the original text scan. One raw data pointer cell at **`main+0x32F0EF8`** contains the exact target `0xCE854C`.

The nearby original data table has `0x32F0ED0=0`, `0x32F0ED8=0` and executable function pointers from `0x32F0EE0` onward. M20.3 initially counted zeros as executable because the NSO text segment starts at RVA 0; this was corrected and successfully rerun. The adjacent function-pointer sequence is **table-like**, but a concrete vtable address point and class identity are not demonstrated.

One further native raw pointer cell at **`main+0x34963B8`** points to **`main+0x32F0ED0`**, at the start of the two-zero prefix. The scan found no bounded ADRP-to-table-neighborhood references. These are **structural pointers only**, not verified constructor stores or a runtime vptr value.

## Reproduction

```bash
python -m pip install "lz4>=4,<5" "capstone>=5,<6"
python -m Scripts.resources.m20_native_species_item_targets --self-test
python -m Scripts.resources.m20_native_species_item_targets
python -m Scripts.resources.m20_1_indirect_provenance --self-test
python -m Scripts.resources.m20_1_indirect_provenance
python -m Scripts.resources.m20_2_schema_dispatch --self-test
python -m Scripts.resources.m20_2_schema_dispatch
python -m Scripts.resources.m20_3_schema_pointer_backrefs --self-test
python -m Scripts.resources.m20_3_schema_pointer_backrefs
```

Results:
- `UnPack/2.0.1/Resources/Pokemon/NativeCallers/M20/m20_original_property_hash_sites.json`
- `UnPack/2.0.1/Resources/Pokemon/NativeCallers/M20/m20_1_rodata_hash_neighborhood.json`
- `UnPack/2.0.1/Resources/Pokemon/NativeCallers/M20/m20_2_original_hash_array_consumer.json`
- `UnPack/2.0.1/Resources/Pokemon/NativeCallers/M20/m20_3_schema_pointer_backrefs.json`
- `UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M20/m20_two_stage_item_callers.json`
- `UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M20/m20_1_original_wrapper_caller_offsets.csv`
- `UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M20/m20_1_native_item_offset_distributions.json`

CI: `unpack-m20-native-species-item-targets.yml`, `unpack-m20-1-indirect-provenance.yml`, `unpack-m20-2-schema-dispatch.yml`, `unpack-m20-3-schema-pointer-backrefs.yml`.

## Next necessary native proof

1. **Pokémon:** trace the native pointer at `main+0x34963B8` to its writer/owner and the table-like region `0x32F0ED0`; follow consumers of the descriptor output `[x1]` from `0xCE857C` and tie the **original 603 distinct source nodes** to an independently validated species/form field. A third property hash is not a species ID.
2. **Items:** prioritize the 17 verified callsites of `main+0x2F1F0`, locate concrete V1/V2 implementations and the **backing memory source of wrapper+8**. Compare multiple live full 68-byte original records to `00983.bin` via the existing read-only GDB probe if static constructors remain ambiguous. Only then interpret `+0x26/+0x3A` by semantic consumers.
3. Preserve `species_id_bindings_verified=0` and `material_type_enum_verified=false` until both source identity and semantic binding are demonstrated.
