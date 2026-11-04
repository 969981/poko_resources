# M5 Pokopia 2.0.1 native texture linkage audit

## Uploaded TSV inputs
- layout-textures.tsv: 9,427 data rows; 4,713 have a zero TEXINFO/G1T pair.
- item-texture-map.tsv: 3,229 data rows with 1,615 distinct item IDs. All 3,229 pairs occur uniquely in layout-textures.tsv.
- item-id-inventory.tsv: 1,615 item ID rows. These files came from the user and retain original provenance under Textures/Indexes.

## Native KIDSOBJDB field evidence
Little-endian 32-bit fields at base offset p, p+0x30 and p+0x34 respectively match object_hash, g1t_hash and texinfo_hash.

| database hash | layout rows | native triple verified |
| --- | ---: | ---: |
| 50ae86ef | 7086 | 7086 |
| e2e43333 | 30 | 30 |
| be0f9d82 | 20 | 20 |
| d418753e | 1378 | 1378 |
| d66dc723 | 10 | 10 |
| ec769edf | 56 | 56 |
| TOTAL | 8580 | 8580 |

All 3,229 item-texture-map pairs refer to those six original databases, and their triples were found at the stated offsets in actual on-branch binary files. The remaining 847 non-item layout rows have NOT received the same level of validation.

Example item 1425 (wooden crate): item_1425_m; TEXINFO 048fc972; G1T d09a60bd; KIDSOBJDB object 9a25ce0c at byte offset 315040, G1T at 315088, TEXINFO at 315092; G1T root_049532_d09a60bd.g1t is 65,588 bytes in 0x00011c54.fdata/native.

## Atlas versus individual textures
1,333 item-base references share (TEXINFO b4b1fe49, G1T a0ce9914); 272 additional base references share (51087a18, 26a15463); 14 share (c8d83a39, 35d04d04). Do not duplicate a whole atlas as individual icons. 1,610 _m mapping entries represent 1,606 distinct IDs. Nine IDs lack an _m row: 3476 and 3592 through 3599. IDs 1677, 1764, 1765 and 2742 are repeated in multiple packs.

## Reproducibility
- Scripts/resources/trace_item_textures.py checks TEXINFO native name, G1T physical byte size, pack identity and the three KIDSOBJDB fields; it generates item_native_link_audit.csv and item_native_link_summary.json.
- Scripts/resources/g1t_to_png.py produces raw format-correct BC7/BC3 PNG decoding candidates using linear and various GOB block heights.
- .github/workflows/unpack-m5-item-links.yml checks four known items and emits candidate previews.

Statuses VERIFIED_NATIVE_FIELDS and PNG_CANDIDATE_UNVERIFIED are intentionally different. Physical hash linkage does not prove pixels, alpha, GOB parameters or atlas UV crop are correct. 1,615 mapped IDs are not the full 3,586 named items; 2,041 named items are still outside this mapping coverage.
