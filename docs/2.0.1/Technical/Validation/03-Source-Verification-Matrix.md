---
title: 原生文件和导出结果证据矩阵
tags: [pokopia, 2-0-1, validation, evidence]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 样本与验证报告矩阵（2026-11-05）

| 对象 | 当前仓库记录的证据 | 下一项必须验证 |
| --- | --- | --- |
| LINKDATA 00983.bin | 文件头 4,600 / v3；每条 68 字节；第 6 条名称索引 = 520；原生报告 0 差异 | 游戏原生加载器与材料分类、最大堆叠消费者调用链 |
| 日语物品名 04645.bin | 3,001×32 的 v2 表、相对指针；源 SHA-256 已入验证报告 | 多语言表之外的任务/场景引用 |
| TEXINFO 单记录 | 108 字节，真实名称 `still_tutorial_123`、layer 0、八个 UV float | 此贴图所属 G1T 的引用和真实像素 |
| 主道具图集 | 1,333 TEXINFO UV 记录与共享 G1T 索引；专用导出器使用 2 层 BC7 / ounce16 | PNG manifest 完整回读与视觉抽样，确认每条独立身份 |
| M7 九语言记录 | 2350–2358 的 row=4、原生偏移、原生控制标签、结构匹配 | 脚本/场景/任务/建筑的直接外键证据 |
| KIDSOBJDB / RNK | 现有格式解析器、M9 跟踪与候选外键调查 | 补足缺失 FDATA 样本、消费字段的原生调用链 |

## 本轮核对的历史结果（不是新跑的测试）

- [原生物品 validation.json](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/validation.json)：`MATCH`、4,600 item slots、0 language mismatches；九语言每种有 3,586 个非空字符串槽（包括 Empty 占位），不能因此写 3,586 个已证明真实物品。
- [M7 报告](../../../../UnPack/2.0.1/Resources/Localization/M7/m7_report.json)：解析 2,738 个文本表、195 组九语言表；仍标记外部引用未验证。
- [原生道具纹理索引审计](../../../../UnPack/2.0.1/Resources/Textures/Indexes/item_native_texture_audit.json)：1,333 主图集关联；报告明确说明旧阶段的 G1T 像素未视觉验收。后续专用导出结果应以 [native_icon_summary.json](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/native_icon_summary.json) 及 manifest 复核。
- [M20 反证](../../M20_ITEM983_CACHE_ORIGIN.md)：OpenSSL NID 983 不是物品表 00983.bin 的原生消费者。

**证据分层**：原始字节可复核 ≠ 索引引用闭合 ≠ 渲染输出正确 ≠ 游戏代码实际消费 ≠ 游戏内语义证明。

入口：[[docs/2.0.1/Technical/Samples/README|Samples]] · [[01-Byte-To-Output-Checklist]] · [[02-Regression-Test-Commands]]。
