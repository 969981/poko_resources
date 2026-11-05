---
title: KIDSOBJDB 对象属性与边界
tags: [pokopia, 2-0-1, kidsobjdb, idok, rdok]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---
# KIDSOBJDB：对象、属性及未解释引用

已实现入口：[decode_kidsobjdb.py](../../../../Scripts/unpack/decode_kidsobjdb.py)；辅助的只读 .NET 命令：§Pokopia.Binary.Cli kids§、§kids-fields§。**本笔记只对已实现的结构读取负责**。

## 1. 文件头（至少 28 字节）

| 偏移 | 类型 | 字段 |
| --- | --- | --- |
| §+0x00§ | 8 bytes | §_DOK0000§ |
| §+0x08§ | u32 | header_size |
| §+0x0c§ | u32 | platform |
| §+0x10§ | u32 | entry_count |
| §+0x14§ | u32 | name_file_hash |
| §+0x18§ | u32 | declared_size |

首块起始偏移为 §align4(header_size)§。记录 §declared_size§ 与实际长度不一致时输出 warning，不应静默修复。

## 2. IDOK 块（固定部分）

§IDOK0000§ (8 bytes) + §u32 block_size§。从块起点 §+0x0c§ 起：§u32 property_name_hash§、§u32 property_type_hash§、§u32 property_count§。**块头共 24 字节**，随后 §property_count§ 个 12 字节属性描述：§(type_code, element_count, property_hash)§，均为 u32 little-endian。

字段值在描述符区之后顺序排列，读取时检查 §element_count × element_width§ 不得越过块尾。支持的类型码（仅表示定长二进制类型，不代表游戏概念）：

| type_code | Python 格式 | 元素字节数 |
| --- | --- | ---: |
| 0 / 1 | §<b§ / §<B§ | 1 |
| 2 / 3 | §<h§ / §<H§ | 2 |
| 4 / 5 | §<i§ / §<I§ | 4 |
| 8 | §<f§ | 4 |
| 10 | §<4f§ | 16 |
| 12 | §<2f§ | 8 |
| 13 | §<3f§ | 12 |

遇到未实现的 type_code 时标记 §PARTIAL_UNSUPPORTED_PROPERTY§，不要按猜测的宽度继续错位解码。

## 3. RDOK 块

§RDOK0000§ 也以 §u32 block_size§ 开头。当前真实样本里已出现长度 **28** 的 RDOK：保留其后四个 u32 原值；已观察到部分记录前三个数相等、末尾为 0，但 §RDOK_WORDS_UNINTERPRETED§ **不是对引用目标的语义证明**。其他长度标记 §RDOK_OPAQUE§。

## 4. 读取命令

§§§powershell
python -m Scripts.unpack.decode_kidsobjdb --input PATH_TO_REAL_KIDSOBJDB --output _meta/kidsobjdb.json --max-sampled-values 32 --max-mib 64
dotnet run --project Pokopia.Binary.Cli -c Release -- kids-fields PATH_TO_REAL_KIDSOBJDB 8
§§§

脚本默认限制单文件 64 MiB，保护内存和失控扫描；大文件请优先使用 .NET 只读辅助程序或针对性样本，不要无证据地提高上限。

## 5. 对象外键的证据等级

§property_hash§、§type_hash§、raw offset、解码值可以作为可靠结构证据，但与物品 ID、物种 ID、任务 ID 的数值相等只产生**候选关联**；必须补充资源对象建立、原生消费者读取及运行时/可复验匹配，才能命名为正式外键。

相关：[[02-RDB-RDX-FDATA-IDRK]]、[[05-Native-Item-00983]]、[[06-Native-Text-Tables]]。
