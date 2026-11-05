---
title: Pokopia 2.0.1 M7 非九语言组原生文本导出与证据边界
aliases: [M7 Unlinked Text Exports, 独立文本表提取]
tags: [pokopia, m7, localization, native-text, provenance]
updated: 2026-11-05
---

# M7 原生文本表：剩余 983 张全量提取

## 结果（以 2.0.1_unpack 分支成功 Actions 为准）

- 原生来源：UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/*.bin。
- M7 清单：UnPack/2.0.1/Resources/Localization/M7/native_table_inventory.csv。
- M7 九语言候选组：UnPack/2.0.1/Resources/Localization/M7/nine_language_groups.csv。
- 原生文本表：2,738 张 PARSED。
- 九语言候选组：195 组 × 9 = 1,755 张，已经通过 M7 全量 TXT 导出工作流发布到 TextExports/。
- 不属于九语言组的独立原生文本表：983 张，其中 974 张为 8 字节索引、9 张为 32 字节索引。
- 本轮 983 张：**162,313 条原生文本记录、174,238 个原生记录/形态槽**。
- 实际新增 983 份 unknown.txt、983 份 unknown.forms.jsonl、983 份 manifest.json。
- [成功执行 #42025049349](https://github.com/969981/poko_resources/actions/runs/42025049349)，包含原生文件与 SHA-256、所有文本 ID、表内形态和 TXT/JSONL 对账。

## 运行方式

在仓库根目录执行：

~~~bash
python -m unittest discover -s tests -p 'test_unlinked_native_text_export.py' -v
python Scripts/resources/export_unlinked_native_text.py
# 只导出某张原生表：
python Scripts/resources/export_unlinked_native_text.py --start-entry 471
~~~

输出目录：UnPack/2.0.1/Resources/Localization/UnlinkedText/table_XXXXX/

每张表：
- **unknown.txt**：一行对应零基 text_id 的一个原生记录，只取原始 form 0；空行保留。物理换行、TAB、反斜杠转义，保留游戏标签。
- **unknown.forms.jsonl**：原始全部形态、原始文本、绝对字节偏移和 u32 元数据。
- **manifest.json**：原生 entry、来源 SHA-256、结构、输出 SHA-256、UNKNOWN 分类和证据等级。
- **unlinked_text_export_report.json**（根目录）：所有 entry、记录数、形态数量、来源哈希及输出路径。

工作流：.github/workflows/unpack-m7-unlinked-text-export.yml。
工作流以 M7 已解析表减去九语言候选表为集合，动态检出 983 份原生文件，逐项验收后才发布。

## 不能越过的语义证据边界

- 语言 UNKNOWN：只表示当前没有可靠的九语言定位，并非文本没有语言。
- category UNKNOWN：没有游戏原生消费端证据前，不根据关键词判断任务、剧情、建筑、UI、教程。
- evidence_grade UNLINKED_NATIVE_RECORD：文本二进制解析已验证，不代表已验证脚本读取来源。
- text_id 是**单张原生表内的零基记录顺序**，不是全局任务或剧情 ID。
- M7 中非 PARSED 的 LINKDATA 文件仍需分别分析其他格式。

## 与 M8/M9 引用证据衔接

M9 verified_resource_text_edges.csv 当前有 5,365 条具备原生布局或固定解析器证据的资源到文本外键：

| 候选九语言组起始 entry | 已证明资源关系 | 边数 |
|---|---|---:|
| 04645 | Items / MapParts | 5,307 |
| 02332 | Reactions | 47 |
| 04942 | Skills | 11 |

没有将这些组的全部文本误标为某一业务分类。这些边也**不是脚本调用链**。
M9/ScriptTextCandidates/m9_numeric_text_tuple_report.json 的 verified_script_to_text_foreign_keys 仍为 0，未得到新的 Quest / Dialogue / Buildings / UI / Tutorials 外键。

后续必须从真实脚本或 ExeFS 消费端证明**调用者对象身份 + 已命名字段与原始偏移 + 文本表 entry + 原生行 ID**，才能升级类别。孤立数值相等不能作为文本外键。

## 关联文档

- [[16-Native-Text-Exports]]：195 组九语言 TXT/JSONL。
- UnPack/2.0.1/Resources/Localization/M7/README.md：原生记录和语言候选规则。
- UnPack/2.0.1/Resources/Localization/M8/m8_report.json：已知外键。
- UnPack/2.0.1/Resources/Localization/M9/README.md：原生对象字段与调用者证据。
