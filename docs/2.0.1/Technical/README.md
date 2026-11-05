---
title: Pokopia 2.0.1 技术知识库
aliases: [Pokopia 技术文档, Pokopia 解包手册]
tags: [pokopia, reverse-engineering, obsidian, documentation]
game_version: "2.0.1"
branch: 2.0.1_unpack
updated: 2026-11-05
---
# Pokopia 2.0.1 技术知识库

> 面向 Obsidian 的原生资源技术手册：**原始来源 → 容器还原 → 结构解析 → 图像/文本转换 → 可查询数据 → 证据核验**。所有路径均相对于仓库根目录。本文是已有研究的入口，不覆盖旧的 M0–M22 研究日志。

## 文档导航

1. [[01-Source-Layout|原始文件、目录和来源规则]]
2. [[02-Binary-Formats|原始二进制格式与读取方法]]
3. [[03-Unpacking-Workflow|7z / LINKDATA / RDB / FDATA 解包]]
4. [[04-Texture-Pipeline|TEXINFO、G1T、Ounce swizzle 与 PNG]]
5. [[05-Localization|原生多语言文本、原文件位置与转换]]
6. [[06-Script-Cookbook|工具与脚本命令速查]]
7. [[07-Data-Usage|导出数据的读取、引用及验收]]
8. [[08-Evidence-And-Open-Questions|证据等级、反证与未完成研究]]
9. [[09-Research-Template|单个格式/资源的研究笔记模板]]
10. [[10-Toolchain-And-Dependencies|工具链安装、输入输出和 .NET 使用边界]]
11. [[11-Format-Details|LINKDATA、RDB/FDATA、KIDSOBJDB、TEXINFO/G1T 原始格式卡片]]
12. [[12-Reproducible-Recipes|Windows PowerShell 完整操作配方]]
13. [[13-Resource-Provenance-Map|从 CSV/PNG/文本反查原始文件位置]]
14. [[14-Troubleshooting-And-Validation|解包故障、回归测试与验收清单]]
15. [[15-Obsidian-Workflow|Obsidian Vault、笔记模板和维护规范]]

以上 Wiki 链接在 Obsidian 中可直接点开；[GitHub 兼容目录](01-Source-Layout.md)可以从浏览器访问。推荐**将整个仓库根目录作为 Obsidian Vault**，这样笔记可以链接到 `Scripts/`、`UnPack/` 和现有 `docs/2.0.1/` 的其他 Markdown 文档。无需提交个人 `.obsidian/` 配置。

## 最先核对的仓库原始资料

- [解包规则](../DIRECTORY.md) · [原有格式研究](../FORMATS.md) · [M3 SQLite](../M3_SQLITE.md)
- [M5 纹理管线](../M5_NATIVE_TEXTURE_PIPELINE.md) · [M9 物种与材料研究](../M9_POKEMON_ITEM_IDENTITIES.md)
- [M17–M19 的最新身份与字段状态](../M17_M19_NATIVE_ID_AND_ITEM_ENUM_STATUS.md) · [M20 NID 983 反证](../M20_ITEM983_CACHE_ORIGIN.md)
- [原生 Resources 总说明](../../../UnPack/2.0.1/Resources/README.md) · [解包脚本说明](../../../Scripts/README.md)

## 知识库维护约定

- 原始数据 **`2.0.1/` 不修改**；正式逐条二进制放在 `UnPack/2.0.1/romfs/`，可用资源和索引放在 `UnPack/2.0.1/Resources/`。
- 每份结论记录源完整路径、游戏版本、SHA-256、条目/结构偏移、转换参数、脚本路径、验证方式；字段未经验证写 `UNKNOWN`，不凭外观推定身份。
- 将历史进度与当前结论分开：旧文档可能保留探索阶段的「尚未支持」文字，优先以**带原始字节及最新审计报告**的研究为准。
- 不将第三方 PokoHex 图片/文本、原生 PNG 候选、原生已证身份视为同一个等级。

## 选择实际工作路线

- 要从 7z/索引开始恢复：[[12-Reproducible-Recipes]] → [[03-Unpacking-Workflow]]。
- 要查某个源文件的字节结构：[[11-Format-Details]] → [[02-Binary-Formats]]。
- 要找一张 PNG 或一条语言文本的原始位置：[[13-Resource-Provenance-Map]] → [[04-Texture-Pipeline]] / [[05-Localization]]。
- 要解决运行错误或核验结果：[[14-Troubleshooting-And-Validation]] → [[08-Evidence-And-Open-Questions]]。
- 要在 Obsidian 新建专题：[[15-Obsidian-Workflow]] → [[09-Research-Template]]。

## 深入专题：字节布局与复现手册（新增）

原有 01–15 为总览，下列新索引按具体二进制格式与转换流程拆分，支持 Obsidian Wiki 链接和 GitHub 相对链接：

- **格式专题**：[[docs/2.0.1/Technical/Formats/README|Formats 格式索引]] · [GitHub 格式目录](Formats/README.md)；包括 LINKDATA IDX/BIN、RDB/RDX/FDATA/IDRK、KIDSOBJDB、TEXINFO/G1T、00983 物品表、原生文本表。
- **完整操作流程**：[[docs/2.0.1/Technical/Workflows/README|Workflows 操作流程]] · [GitHub 操作目录](Workflows/README.md)；包括分卷还原、纹理 PNG 生成、九语言 CSV/JSON。

专题中的结构、偏移、错误码以链接的当前解析脚本为依据；未完成的物种 ID、材料枚举及任务/建筑外键仍为待验证结论。

更新日期：2026-11-05。

## 真实样本与验收手册（2026-11-05）

- **真实 Hex 样本**：[[docs/2.0.1/Technical/Samples/README|Samples 样本索引]] · [GitHub 浏览](Samples/README.md)。覆盖 00983.bin、04645.bin、108 字节 TEXINFO、M7 九语言偏移及导出来源。
- **质量门禁 / 回归**：[[docs/2.0.1/Technical/Validation/README|Validation 验收索引]] · [GitHub 浏览](Validation/README.md)。覆盖 byte-to-output provenance、已有测试命令、仓库历史审计和未完成外键。
- 上述 Hex 来自仓库中真实文件的本次读取；源文件 SHA-256 以已提交报告核对；**未重跑全部本地 ROM 解析与 PNG 导出**。

## 按资源分类查原始路径、图片导出与 Hex（2026-11-05）

**[[docs/2.0.1/Technical/Resources/README|Resources 资源路径百科]]** · [GitHub 目录](Resources/README.md)：针对物品/食材/材料、表情、村民头像、技能、宝可梦、UI 场景等，整理原始 RomFS→TEXINFO/G1T→PNG/CSV 路径、Hex 字段、分类候选和可执行的 PowerShell 查询。

重点：[[docs/2.0.1/Technical/Resources/02-Items-And-Native-Kinds|物品分类原值]] · [[docs/2.0.1/Technical/Resources/03-Reactions-Villagers-Skills|表情/村民/技能]] · [[docs/2.0.1/Technical/Resources/05-Image-Export-Guide|图片导出]] · [[docs/2.0.1/Technical/Resources/06-Hex-Format-And-Lookup|真实十六进制示例]]。PokoHex 参考与原生 2.0.1 明确分级，未经代码证明的材料枚举及数量上限仍保留 UNKNOWN。

## 最新：原生 TXT 导出

- [[16-Native-Text-Exports]] — M7 四个九语言锚点的实际 TXT/JSONL、SHA 校验及全组导出命令。
