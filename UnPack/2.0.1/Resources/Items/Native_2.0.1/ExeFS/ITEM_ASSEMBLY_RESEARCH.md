# Pokopia 2.0.1 ExeFS original instruction candidates

Source: 2.0.1/exefs/main
SHA-256: 8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f
Status: candidate only. No native field consumer or 99-stack limit proven.

## Opcode counts (not semantic proof)

- cmp:0x100:cmp_w: 591
- cmp:0x100:cmp_x: 157
- cmp:0x44:cmp_w: 45
- cmp:0x44:cmp_x: 11
- cmp:0x63:cmp_w: 406
- cmp:0x63:cmp_x: 48
- cmp:0x64:cmp_w: 232
- cmp:0x64:cmp_x: 36
- cmp:0xff:cmp_w: 1323
- cmp:0xff:cmp_x: 1537
- load:0x22:ldrb: 860
- load:0x22:ldrh: 410
- load:0x26:ldrb: 1804
- load:0x26:ldrh: 239
- load:0x2a:ldrb: 86
- load:0x2a:ldrh: 222
- load:0x39:ldrb: 252
- load:0x3a:ldrb: 333
- load:0x3a:ldrh: 52
- load:0x41:ldrb: 448
- load:0x42:ldrb: 126
- load:0x42:ldrh: 384
- load:0x8:ldr_w: 23802
- load:0x8:ldr_x: 73872
- load:0x8:ldrb: 5477
- load:0x8:ldrh: 4332
- movz:0x100:movz_w: 1571
- movz:0x100:movz_x: 27
- movz:0x11f8:movz_w: 53
- movz:0x44:movz_w: 1198
- movz:0x44:movz_x: 1
- movz:0x63:movz_w: 82
- movz:0x64:movz_w: 1906
- movz:0x64:movz_x: 10
- movz:0xff:movz_w: 3456
- movz:0xff:movz_x: 2

## Manual audit required

1. Recover the producer of the base register at candidate +0x26/+0x3A loads.
2. Tie it to item ID indexing and the 68-byte original item-record layout.
3. Trace add/split/merge and quantity writeback for #99 or #100 comparison.
4. Validate using gameplay examples in multiple item groups.
Do not copy 99 to every item as an evidence-backed native max_stack field.
