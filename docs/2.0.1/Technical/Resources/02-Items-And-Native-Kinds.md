---
title: 原生物品分类字节与材料候选
tags: [pokopia, resources, items, hex, classification]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 物品 / 食材 / 家具 / 素材：原始字段与来源

原生 `00983.bin`：64-byte 文件头（count 4600，version 3），**4600×68 bytes**；SHA-256：
`2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`。

```text
record_start = 64 + item_id * 68
record +0x22: u16 little-endian   已证九语言 name index
record +0x26: u8                  强分类候选，官方枚举未证
record +0x39: u8                  另一分组候选，语义未证
record +0x3A: u8                  另一分组候选，语义未证
record +0x08/+0x0C/+0x10/+0x14: u32 原值，非已证价格/数量
native_max_stack: UNKNOWN         没有找到已证明的逐物品上限字段
```

## +0x26 的实际取值分布

**偏移 `+0x26` 是十六进制，等于记录内第 38 字节。** 以下“原生值”列十进制为 CSV 保存形式，括号内是对应的十六进制字节。统计范围仅有名称的 3,585 个 ID（排除 ID 0 的 Empty），数据来自 [native_item_field_analysis.json](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/native_item_field_analysis.json)。

| 值 | 数量 | 观测样本类别（不是官方枚举） |
| --- | ---: | --- |
| 0 (`00`) | 2 | 特殊候选 |
| 4 (`04`) | 142 | 靠垫、桌子等家具 |
| 5 (`05`) | 165 | 脚手架、隔板等 |
| 6 (`06`) | 930 | 彩花炮、星星碎片，混合 |
| 8 (`08`) | 228 | 墙、泥土和地形 |
| 10 (`0A`) | 383 | 种子/植物 |
| 11 (`0B`) | 393 | 装饰架等 |
| 12 (`0C`) | 34 | 派对咖喱、潜水艇，混合 |
| 13 (`0D`) | 94 | 路灯、露营锅等 |
| 14 (`0E`) | 68 | 建筑套组 |
| 15 (`0F`) | 60 | 食物、蘑菇、海藻 |
| 16 (`10`) | 48 | 藤蔓绳、砖、矿石等材料候选 |
| 17 (`11`) | 22 | 奖状、徽章等 |
| 18 (`12`) | 925 | 灯笼、沙发等大混合组 |
| 19 (`13`) | 91 | 画布类 |

不可根据相同的原生值批量填写正式 `material_type`。尤其 6/18 混杂多个用途。材料公开参考交叉比对虽覆盖 `0x10` 的 48 条，但 [材料证据报告](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/native_material_candidate_summary.json) 仍为 `official_native_enum_name_verified=false`。

## 两条真实物品记录

| 属性 | ID 6 成熟的蘑菇 | ID 101 藤蔓绳 |
| --- | --- | --- |
| 记录文件偏移 | 472 / `0x1D8` | 6932 / `0x1B14` |
| `+0x22` 名称索引 | `08 02` → 520 | `FA 08` → 2298 |
| `+0x26` 原始分类候选 | `0F` → 15 | `10` → 16 |
| `+0x39` | 1 | 1 |
| `+0x3A` | 7 | 6 |
| 原生最大堆叠值 | 未知 | 未知 |

**不能把存档数量 u8 的 0–255 表示范围、正常游戏可能的 99 上限、背包格数和原生每物品堆叠配置混为一谈。** 原生 `native_max_stack` 保持空白。

## 原生图片和引用路径

主道具纹理从 `root_042753_b4b1fe49.texinfo` 与 `root_038147_a0ce9914.g1t` 提取 1,333 张；另有次图集 272 张、特殊 14 张。总共 **1,619 条原生 PNG，1,615 个唯一物品 ID**。四个重叠 ID 为 1677、1764、1765、2742，保留多个图集版本，不能互相覆盖。

查询 [native_icon_complete_catalog.csv](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/native_icon_complete_catalog.csv) 的 `native_png/source_g1t_hash/source_texinfo_hash`；原生 HEX 原值在 [native_item_raw_fields.csv](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/native_item_raw_fields.csv)。

```powershell
python -m Scripts.resources.analyze_native_item_fields --root . --out _work/item-fields
python -m Scripts.resources.export_native_item_atlas --help
```

本脚本 SHA 检查不可绕过后声称是同版原始语义。参见 [[06-Hex-Format-And-Lookup]]。
