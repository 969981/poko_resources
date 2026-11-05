---
title: 原生文本表与九语言字节布局
tags: [pokopia, 2-0-1, localization, text, utf8]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---
# 原生文本表：索引、相对指针与九语言

解析代码：[recover_native_text_ids.py](../../../../Scripts/resources/recover_native_text_ids.py)。输入目录为 §UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/§，其中 §NNNNN.bin§ 是 **LINKDATA 条目编号**，并非剧情文本 ID。

## 1. 已支持的文本表结构

脚本严格要求文件 ≥72 字节，读取：

| 偏移 | 类型 | 说明 |
| --- | --- | --- |
| §+0x00§ | u32 | count，支持范围 1..200000 |
| §+0x04§ | u32 | version 原值 |
| §+0x08..0x3F§ | bytes | 56 字节必须为零（当前可识别类型） |
| §+0x40§ | u32 | 首个相对指针值，用于判定每条记录宽度 |
| §+0x40..§ | 每条 8 或 32 bytes | 由首指针与 count 推得的 index/table |

相对指针规则：§absolute_offset = (64 + row * width + field_index * 4) + relative_u32§。目标必须在索引区之后、文件之内，内容必须是有 NUL 终止的严格 UTF-8。

- **宽 8**：1 个文本形式 + 1 个元数据 u32；
- **宽 32**：6 个文本形式 + 2 个元数据 u32；
- 文本最多扫描 131,072 字节，字节偏移、空字符串和原始 metadata 必须保留；
- 私有使用区字符、原生控制标签不应改写成问号，不应以换行过滤方式重新排列 slot。

§native text_id§ 在当前 parser 中是**原生表内部零基行号**，不等价于任务 ID / 建筑 ID / 脚本枚举。

## 2. 已对账的物品名称九语言

| 条目 | 语言 | 条目 | 语言 | 条目 | 语言 |
| --- | --- | --- | --- | --- | --- |
| 04645 | 日语 jp | 04646 | 英语 en | 04647 | 法语 fr |
| 04648 | 意大利语 it | 04649 | 德语 de | 04650 | 西班牙语 es |
| 04651 | 繁体中文 zht | 04652 | 韩语 ko | 04653 | 简体中文 zhs |

这是 **4,600 行物品名称**已核验链路；其他语种连续分组仅可证明表内部结构对齐，不意味着整套对话、剧情、UI、建筑文本均已分类。

## 3. 可复现转换

§§§powershell
python -m Scripts.resources.discover_native_text --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.recover_native_text_ids --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.export_native_localization --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.link_native_text_references --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
§§§

主要产物：§Resources/Localization/M7/native_table_inventory.csv§、§nine_language_groups.csv§、§native_records_*.csv§，及 §Resources/Localization/Indexes/§ 的索引报告。§export_native_localization§ 需要既有的 §Resources/Items/item_catalog.csv§ 和 §Items/Native_2.0.1/validation.json§ 来验证物品名；其余 tagged-text 扫描结果为未证候选。

## 4. 质量要求

逐条记录原始解码文件 SHA、§entry§、§text_id§、§form_index§、§absolute_byte_offset§、原字符串和控制符。后续追踪场景/任务/建筑，必须证明外部脚本/对象字段真正引用了 §table_id + text_id§ 的组合。

相关：[[05-Native-Item-00983]]、[[../Workflows/03-Localization-To-CSV]]、[[../README|技术首页]]。
