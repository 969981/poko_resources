---
title: Pokopia 2.0.1 原生文本 TXT 导出
aliases: [Pokopia Text Exports, 文本导出]
tags: [pokopia, localization, text, m7]
updated: 2026-11-05
---

# 原生文本导出（M7 → TXT / JSONL）

原生来源：UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/*.bin。
分组证据：UnPack/2.0.1/Resources/Localization/M7/nine_language_groups.csv。
SHA-256 基线：UnPack/2.0.1/Resources/Localization/M7/native_table_inventory.csv。

## 2026-11-05 全量九语言表组导出（已执行并验证）

- M7 候选九语言表组：**195 / 195**；其中包含先前已验证的四个锚点。
- 关联原生 LINKDATA 文件：**1,755 / 1,755**；九语言 TXT：**1,755 个**；全形态 JSONL：**1,755 个**；逐组 manifest：**195 份**。
- 对齐记录和原生形态槽总数：**74,089**（所有组中未展开形态的记录总计 59,084）。该数不应误写为 74,089 个独立文本 ID。
- 每个原始二进制文件通过 M7 inventory SHA-256/status 校验；生成文件验证 SHA-256、零基文本 ID 顺序、所有 form、offset 和 TXT 对应关系。
- 全量工作流：[unpack-m7-all-text-export.yml](../../../.github/workflows/unpack-m7-all-text-export.yml)；成功执行记录：[42023043520](https://github.com/969981/poko_resources/actions/runs/42023043520)。
- 发布目录：[TextExports](../../../UnPack/2.0.1/Resources/Localization/TextExports) 和 [text_export_report.json](../../../UnPack/2.0.1/Resources/Localization/TextExports/text_export_report.json)。

原先的四组工作流 `unpack-m7-text-export.yml` 现在只在临时目录验收锚点，不会回写或覆盖 195 组正式发布报告。全量工作流在原生解析器、导出器或 M7 索引变化时自动重新验证和发布。

**范围说明：**195 组是 M7 已识别的全部 *九语言候选组*，不等于全部 2,738 个已解析原生文本表均已独立发布，也不等于剧情、任务、UI 的原生语义引用链已经闭合。结构证据较弱的四组仍维持 `STRUCTURE_ONLY`；无原生调用证据的 category 仍为 `UNKNOWN`。

## 其他已解析文本与完整证据目录

M7 所有 2,738 张已解析文本表中，195 组九语言候选覆盖 1,755 张；其余 983 张已经使用独立导出器发布到 UnlinkedText/，参见 [[17-Unlinked-Native-Text-Exports]]。

新建 TextCatalog/ 统一索引了这 2,738 张表及 M9 已有的 5,365 条类型化资源外键。M8 的反应动作（02332–02340）和技能（04942–04950）18 张表虽然没有通过 M7 严格连续九语言匹配，但可通过固定版本的 M8 解析器识别；不能把它们误判为毫无来源的未知表。

## 重建命令

    python -m unittest discover -s tests -p test_native_text_file_export.py -v
    # 默认四个九语言锚点：02323、02350、03304、04645
    python Scripts/resources/export_native_text_files.py
    # 导出指定 M7 表组
    python Scripts/resources/export_native_text_files.py --start-entry 3304
    # 导出全部 195 个九语言候选表组（需要完整 decoded 数据）
    python Scripts/resources/export_native_text_files.py --all-groups

## 输出

目录：UnPack/2.0.1/Resources/Localization/TextExports/table_03304/

- jp.txt、en.txt、fr.txt、it.txt、de.txt、es.txt、zht.txt、ko.txt、zhs.txt：每行对应一个零基 text_id，只取 form_index 0；保留空行和原生游戏控制标记。
- lang.forms.jsonl：逐 record 保留全部原始 form、字符串原文、绝对字节偏移和原始 u32 元数据。六形态表的其余五个 form 不会在 TXT 中丢失。
- manifest.json：记录来源、原生文件和导出文件 SHA-256、原始记录数量和证据等级。
- TextExports/text_export_report.json：完成组及尚未覆盖范围。

TXT 把真实的 LF、CR、TAB 和反斜杠分别转义为反斜杠加 n/r/t/反斜杠，以避免字符串内换行导致行号错位。游戏标记如 <br>、<clear>、颜色标签、振假名、PUA 字符保持不变。需还原时以 JSONL 为无损来源。

## 验收边界

本导出调用现有 M7 8/32 字节原生文本表解析器，校验 SHA、status、count、stride、九语言结构 key。缺文件、哈希不符或格式变化则明确失败。

M7 的结构相同只说明候选九语言表对齐，不等于游戏内的场景、剧情、任务、教程或建筑引用已得到证明。没有调用链证据时 category 保持 UNKNOWN；不把 MapPart 当 Buildings，也不把原生记录 ID 当任务 ID。

相关：05-Localization.md、M7/README.md、M8/m8_report.json。
