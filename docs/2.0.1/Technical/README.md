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

更新日期：2026-11-05。