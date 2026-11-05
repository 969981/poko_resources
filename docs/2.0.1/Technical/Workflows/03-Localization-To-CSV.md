---
title: 原生语言文本导出与CSV校验
tags: [pokopia, 2-0-1, text, localization, csv]
game_version: "2.0.1"
status: ACTIVE
updated: 2026-11-05
---
# 解码文本 → 九语言 CSV/JSON → 反查原文件

## 源文件定位

- 解码根：§UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/§。
- 物品原始结构：§00983.bin§；物品名：§04645.bin§ 至 §04653.bin§。
- 先确认 **已解码文件** 存在；如果只有 LINKDATA 索引，回到 [[01-Restore-And-Decode]]。

## 执行

§§§powershell
python -m Scripts.resources.discover_native_text --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.recover_native_text_ids --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.export_native_localization --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.link_native_text_references --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
§§§

对可复验的物品名链路，§export_native_localization§ 还读取 §Resources/Items/item_catalog.csv§ 与 §Resources/Items/Native_2.0.1/validation.json§；校验不到 §MATCH§ 时应失败，不改成无条件导出已验证数据。

## 验收检查

| 检查 | 最低条件 |
| --- | --- |
| 源版本 | 2.0.1，记录每个 decoded SHA-256 |
| 物品 slot | 4,600 行，§item_id§ 0..4599；不得删空行 |
| 九语言 | jp/en/fr/it/de/es/zht/ko/zhs 各自按来源条目保留 |
| 控制字形 | 不能丢 §<oneline>§、PUA、原始控制序列 |
| 文本行号 | 结构表内 §text_id§ 是零基，不是剧情 ID |
| 外键 | 未与原生消费点闭合则保持 §UNKNOWN§ |

M7 原生输出可检查 §Resources/Localization/M7/native_table_inventory.csv§、§nine_language_groups.csv§，不要将语种连续分组误当作场景/剧情分类已完成。

参见 [[../Formats/06-Native-Text-Tables]]、[[../Formats/05-Native-Item-00983]]、[[../13-Resource-Provenance-Map]]。
