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
