---
title: 00983.bin 物品记录与原生字段
tags: [pokopia, 2-0-1, item, native, 00983]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---
# LINKDATA 00983.bin：物品原始记录

真实解码输入：`UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin`。

[分析实现](../../../../Scripts/resources/analyze_native_item_fields.py) 锁定 2.0.1 样本 SHA-256：

`2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`

## 1. 文件级不变量

```text
header_size  = 64 bytes
record_count = 4600
record_size  = 68 bytes
file_size    = 64 + 4600 * 68 = 312864 bytes
row_offset(item_id) = 64 + item_id * 68
```

文件 `+0x00` 是 u32 count（4,600）；`+0x04` 是 u32 version（3）。条目采用从 0 开始的槽号，读第 n 条前必须先确保 `0 <= n < 4600`。这些是 **解析器对指定 SHA 样本的校验条件**，不要直接推广到其他更新版本。

## 2. 每条记录的已读原始字段

| 条目相对偏移 | 类型 | 目前的证据 / 限制 |
| --- | --- | --- |
| `+0x08,+0x0C,+0x10,+0x14` | u32×4 | 原值，语义未统一确定 |
| `+0x22` | u16 | 已与原生九语言名称索引对账 |
| `+0x26,+0x27` | u8×2 | 可能与分类有关，**正式枚举未证明** |
| `+0x2A,+0x2B` | u8×2 | 原值 |
| `+0x36..+0x3B` | 6×u8 | 原值/分组候选 |
| `+0x41,+0x42` | 2×u8 | 原值 |

脚本保留 `raw_record_hex`，并将 `native_max_stack` **留空**；不应把 `+0x26` / `+0x3A` 直接命名为官方材料类型或堆叠上限。存档单字节可表达的数量区间与游戏实际允许持有/堆叠上限是两个问题。

## 3. 只读复验

```powershell
python -m Scripts.resources.analyze_native_item_fields --help
python -m Scripts.resources.export_native_localization --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
```

`analyze_native_item_fields` 还要求本地有九语言名称的既有验证文件；先用 `--help` 查看当次代码参数，**不要**使用 `--allow-other-sha` 绕过版本验证后声称官方字段已确定。输出参考 `Resources/Items/Native_2.0.1/native_item_raw_fields.csv`。

## 4. 未完成证据

必须把“原生资源结构 → ID 到记录定位 → 消费字段的原生指令/运行时值 → 语义检验”闭合才能正式赋义。**ExeFS 中 OpenSSL NID 983 与 `00983.bin` 无关**，不能使用该误匹配充当 loader 证据；参见 [M20 原始反证](../../M20_ITEM983_CACHE_ORIGIN.md)。

相关：[[06-Native-Text-Tables]]、[[03-KIDSOBJDB-IDOK-RDOK]]、[[../Workflows/03-Localization-To-CSV]]。
