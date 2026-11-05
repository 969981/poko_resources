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

## M7/M8/M9 统一文本证据目录（已执行）

新增可重复执行的目录建设工具：

~~~bash
python -m unittest discover -s tests -p 'test_native_text_catalog.py' -v
python Scripts/resources/build_native_text_catalog.py
~~~

- Actions：[M7/M9 Verified native text provenance catalog](https://github.com/969981/poko_resources/actions/workflows/unpack-m7-m9-text-catalog.yml)。
- 输出目录：UnPack/2.0.1/Resources/Localization/TextCatalog/。
- native_text_table_catalog.csv：全部 2,738 张已解析表的来源、布局、语言证据与导出路径。
- m9_verified_text_row_links.csv：已验证的 5,365 条 **M9 类型化资源→文本行** 边及来源字段；不会冒充脚本调用。
- m9_verified_group_domain_summary.csv：三个表组与四类关系的分布。
- native_text_catalog_report.json：覆盖报告、已知角色来源和未知范围。

**关键修正：**原始 M7 结构对齐规则排除了 02332–02340 的 Reactions 和 04942–04950 的 Skills，但 M8 的固定版本能力解析器及对应原生记录为这两组分别提供了可靠的九语言顺序及角色表身份。因此在 983 张 M7 unlinked 表中，**18 张在统一目录中升级为 M8_PINNED_NATIVE_ROLE_MAPPING，另 965 张仍 UNKNOWN**。原始 UnlinkedText 仍作为不猜语种的无损底层导出，不改变其 source-provenance manifest。

三个已有关系表组中，只有 04645 属于 M7 195 个结构候选组；02332 和 04942 是 M8 单独来源验证组。这个区分对后续识别使用者非常重要。

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


## M7.1 结构与原文复查（2026-11-05）

已增加 [[18-Native-Text-Families]]：使用 983 张原始二进制及其 M7 SHA-256 基线重新扫描，得到 22 组具有九文件唯一结构和文字脚本证据的候选（198 张表）、61 个歧义长区间位置（549 张）、18 个低内容区间（162 张）、56 张不成组文件。M8 已知的两组原生角色表（18 张）用作正向对照，因此仍有 965 张身份没有通过原生读取者验证。

候选文件见 UnPack/2.0.1/Resources/Localization/TextFamilies/nine_language_hypotheses_NOT_VERIFIED.csv。它不改变原始 TXT、manifest 和正式 TextCatalog 的身份字段；视觉/词义线索只用于缩小后续 ExeFS/Lua/资源消费者验证范围。
