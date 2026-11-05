---
title: 文本原始位置与语言转换
tags: [pokopia, localization, text, multilingual]
updated: 2026-11-05
---
# 原生多语言文本的位置、解析和导出

## 已验证：九语言物品名称

所有条目都在 `UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/`，先从原始 `2.0.1/romfs/LI_C0_R.IDX` + 恢复后的 `LD_C0_R.BIN` 按 [[03-Unpacking-Workflow]] 提取。

| 语言 | LINKDATA 条目 / 原始解码文件 |
| --- | --- |
| 日文 jp | `04645.bin` |
| 英文 en | `04646.bin` |
| 法文 fr | `04647.bin` |
| 意大利文 it | `04648.bin` |
| 德文 de | `04649.bin` |
| 西班牙文 es | `04650.bin` |
| 繁体中文 zht | `04651.bin` |
| 韩文 ko | `04652.bin` |
| 简体中文 zhs | `04653.bin` |

物品结构数据：同目录 `00983.bin`，4,600 条 68 字节记录。名称索引字段 `+0x22` 的九语言对账结果见 `UnPack/2.0.1/Resources/Items/Native_2.0.1/validation.json`；九语言各 4,600 个原始槽位，不等于全部都有非空名称。

供应用读取的 UTF-8 文件：`UnPack/2.0.1/Resources/Items/Text/text_item_<lang>.txt`。**零基行号即物品 ID**，不能排序、删除空行、去重或自动将同名项合并。PokoHex 来源的文本文件与已核验的原版链路须在来源字段中区分。

## 已有的其他原生文本结构解析（M7）

`Scripts/resources/recover_native_text_ids.py` 读取解包 `*.bin` 中经边界检测的原生候选文本表。已观察到两类记录宽度 **8 / 32 字节**，索引起点 **0x40**，字符串指针为相对于字段自身的偏移，文本为 UTF-8 NUL 终止。保留原始控制符、原生私用区字符（PUA）、空槽、`form_index`、字节位置和 SHA。

这一步得到的是**表内零基文本序号**、语言结构对齐和候选九语对照；尚不能据此确认场景、剧情、任务或建筑使用的外键，也不能把六个 form slot 命名成官方语法意义。

## 实际命令

```bash
# 从真正的 LINKDATA decoded/ 目录读取
python -m Scripts.resources.discover_native_text --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.export_native_localization --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.recover_native_text_ids --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
# 限定少数待核对原生候选（不是已验证的剧情表）
python -m Scripts.resources.discover_native_text --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded --entries 2324 2351 3305 --dest UnPack/2.0.1/Resources/Localization/Samples
```

脚本分别产出：
- `discover_native_text.py`：`source_files.csv`、`text_candidates.csv`、`discovery_report.json`；为 UTF-8 标签的**候选扫描**。
- `export_native_localization.py`：经验证物品九语言对照和 `native_text_candidates.csv`；候选的语言/类别可能为未知。
- `recover_native_text_ids.py`：默认 `Resources/Localization/M7/` 的分片 CSV/JSON 与 `m7_report.json`；表号、`text_id`、`form_index`、原始偏移及九语言结构对照。
- `link_native_text_references.py` 及 M8/M9 分析脚本继续寻找真实引用边，不能用简单整数相等代替关系证明。

## 未完成类别

`Dialogue`、`UI`、`Quest`、`Buildings`、`Tutorials`、`Scene` 的语义分类，须取得真实脚本/对象字段 → 文本表编号 → 行 ID 的证据。`_RNK0000` 属性名称 / 相关 FDATA 不全时，分类必须保持 `UNKNOWN`。九语言物品名称已验证**不等于全游戏九语言已提取完成**。

参考：[Localization 实际状态](../../../UnPack/2.0.1/Resources/Localization/README.md)、[M9 属性和物种关联研究](../M9_POKEMON_ITEM_IDENTITIES.md)、[[08-Evidence-And-Open-Questions]]。