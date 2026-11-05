---
title: 真实Hex布局与内部字段读取
tags: [pokopia, resources, binary, hex, fields]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 内部数据格式：原始十六进制与字段

**偏移 vs 值**：`+0x26` 是记录内的第 **38** 个字节偏移；这个位置的原始值可能是 `0F` (=15) 或 `10` (=16)。不能把“`0x26` 偏移”当成“分类值 26”。

## 1. 真实物品记录（LINKDATA 00983.bin）

源：`UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin`，312,864 bytes，SHA-256 `2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`。

| 位置 | 原始字节/类型 | 已证含义 |
| --- | --- | --- |
| 文件 `0x00` | `F8 11 00 00` u32 LE | count=4600 |
| 文件 `0x04` | `03 00 00 00` u32 LE | table_version=3 |
| 第 n 条 | `0x40+n*0x44` | 记录长 `0x44=68` bytes |
| 记录 `+0x22` | item 6 = `08 02` u16 LE | 名称索引 520 |
| 记录 `+0x26` | item 6 = `0F` / item 101 = `10` | 分类候选 15 / 16，官方枚举未证 |
| 记录 `+0x39/+0x3A` | item 6 = `01/07` | 原始分组候选 |

```powershell
$source = "UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin"
$id = 101
$b = [IO.File]::ReadAllBytes($source)
if ($b.Length -ne 312864) { throw "Unexpected item table" }
$at = 64 + $id * 68
[pscustomobject]@{
  ItemId=$id
  FileOffset=('0x{0:X}' -f $at)
  NameIndex=[BitConverter]::ToUInt16($b,$at+0x22)
  KindHex=('0x{0:X2}' -f $b[$at+0x26])
  Group39=('0x{0:X2}' -f $b[$at+0x39])
  Group3A=('0x{0:X2}' -f $b[$at+0x3A])
}
[BitConverter]::ToString($b,$at,68)
(Get-FileHash $source -Algorithm SHA256).Hash.ToLowerInvariant()
```

物品 ID 101 的预期：`FileOffset 0x1B14`、`NameIndex 2298`、`KindHex 0x10`、Group39 `0x01`、Group3A `0x06`。原始 68 字节全量 Hex 已保存在 [native_item_raw_fields.csv](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/native_item_raw_fields.csv)。

## 2. 真实 G1T 图像头

原生文件 `UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/root_017070_47b4eb66.g1t` 为 **4148 字节**；本轮按原字节核实：

```text
00  47 54 31 47 30 36 30 30   "GT1G0600"
08  34 10 00 00               declared_length = 0x1034 = 4148
0C  1C 00 00 00               table_offset = 0x1C
10  01 00 00 00               texture_count = 1
14  18 00 00 00               platform = 0x18
1C  04 00 00 00               relative_texture_offset = 4
20  10 66 66 00 11 10 21 10   8-byte texture descriptor
       ^^                     format = 0x66 = BC7
          ^^                  dxdy = 0x66 → width=64, height=64
```

纹理描述符起点是 `table_offset + relative_texture_offset = 0x20`。Ounce 平台块排列不同于旧版 Tegra GOB，不能仅根据输出 PNG 可打开就判定 swizzle 正确。

## 3. 对应的 TEXINFO UV

同一 `native/` 目录 `root_000147_00a2d79b.texinfo` 为 **108 字节**：

```text
file +0x00    u32 count = 1
file +0x04    64-byte ASCII name = icon_poke_uni_0180_00_00_00
file +0x44    u32 layer = 0
file +0x48    8 × little-endian f32:
              [0,0,0.75,0,0,0.75,0.75,0.75]
file +0x68    u32 tail = 1（语义未定）
```

该 TEXINFO/G1T 配对从 64×64 画布裁切为 48×48 候选图；`0180` 只是纹理名称数字，不是已证 species_id。通常 TEXINFO 为 `4 + count×104` bytes，记录相对偏移与文件绝对偏移相差 4 bytes。

## 4. KIDSOBJDB 与原始对象字段

- 文件头 `_DOK0000`；IDOK 块头 `IDOK0000`、RDOK 块 `RDOK0000`。
- IDOK 属性描述符为 12-byte：type_code、element_count、property_hash（均小端 u32）。
- 0/1 对应 i8/u8，2/3 对应 i16/u16，4/5 对应 i32/u32，8 对应 f32，12 对应 vec2 f32，13 对应 vec3 f32。
- `object_hash`、`property_hash`、`type_hash` 不是物品 ID；数值匹配仅得到候选关联。

参见 [KIDSOBJDB 格式](../Formats/03-KIDSOBJDB-IDOK-RDOK.md) 与 [G1T/TEXINFO 格式](../Formats/04-TEXINFO-G1T.md)。

## 5. PokoHex 小二进制（参考来源）

已直接从固定提交读取：

- `PokoHex.Core/Resources/byte/item_menuicon.bin`：9200 bytes = 4600 × u16；ID 6 处 `06 00`，不是已证的原生纹理偏移。
- `PokoHex.Core/Resources/byte/villager_portrait.bin`：2100 bytes = 1050 × u16；ID 49 处 `03 00` 指向 portrait ID 3；**不是原生 2.0.1 的角色表证据**。

内部 8/32-byte 原生文本索引与原始相对指针，请阅读 [[07-Languages-And-Resource-Search]] 和 [M7 样本](../Samples/04-M7-Nine-Language-Trace.md)。
