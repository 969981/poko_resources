---
title: 00983.bin 原始字节样本
tags: [pokopia, 2-0-1, samples, hex, item]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 00983.bin：真实物品记录 Hex

> 证据定位：LINKDATA 解码后的物品表，不等于已证明的游戏运行时读取调用链。

**源文件**：`UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin`

**源文件 SHA-256（仓库 validation.json）**：`2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`

**原始长度**：312,864 字节；校验规则由 [verify_native_items.py](../../../../Scripts/resources/verify_native_items.py) 实现。

## 真实文件头（从 0x00 读取的前 16 字节）

~~~text
offset  raw bytes
0x00    f8 11 00 00 03 00 00 00 00 00 00 00 00 00 00 00
        └─ 0x11f8 = 4600  └─ version = 3
~~~

- 头宽：64 字节；记录宽：68 字节；记录数：4,600。
- 第 n 条起点：`64 + n × 68`；第 6 条起点 `472 = 0x1D8`。
- 第 6 条在记录内 `+0x22` 的 2 字节为 `08 02`，小端值 **520**；全文件偏移 `0x1FA`。
- [原生目录](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/native_item_catalog.csv) 对应 CSV：item_id = 6、native_name_index = 520、en = `cave mushrooms`、jp = `たべごろキノコ`、zhs = `成熟的蘑菇`。
- [已提交校验结果](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/validation.json) 为 `MATCH`、`differences=0`、九种语言每种 4,600 槽；仅证明原生物品名称对账。

## 第 6 条完整 68 字节（原始，未赋予未经证实的字段语义）

~~~text
00 00 00 00 00 00 00 00 0a 00 00 00 02 00 00 00
0d 00 00 00 21 00 00 00 00 00 ec 2b 27 00 a4 03
10 00 08 02 00 00 0f 00 00 00 01 01 00 00 00 00
00 00 00 00 00 00 00 01 00 01 07 00 00 00 00 02
00 14 04 00
~~~

此处 `+0x26/+0x3A` 及其他原值尚不能称为“官方材料分类”或“最大持有数量”。相关反证见 [M20](../../M20_ITEM983_CACHE_ORIGIN.md)。

## Windows PowerShell 逐字节回读

~~~powershell
$path = "UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin"
$b = [System.IO.File]::ReadAllBytes($path)
if ($b.Length -ne 312864) { throw "Unexpected file size" }
$count = [BitConverter]::ToUInt32($b, 0)
$version = [BitConverter]::ToUInt32($b, 4)
$off = 64 + 6 * 68
$nameIndex = [BitConverter]::ToUInt16($b, $off + 0x22)
[pscustomobject]@{ Count=$count; Version=$version; ItemId=6; RecordOffset=$off; NameIndex=$nameIndex }
[BitConverter]::ToString($b, $off, 68)
(Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
~~~

期望得到 `Count=4600`、`Version=3`、`RecordOffset=472`、`NameIndex=520`。SHA 不符时停止宣称当前样本与 2.0.1 基准完全一致。

源码：[字段分析](../../../../Scripts/resources/analyze_native_item_fields.py) · [九语言校验](../../../../Scripts/resources/verify_native_items.py)；参见 [[docs/2.0.1/Technical/Formats/05-Native-Item-00983]]。
