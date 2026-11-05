---
title: 真实原始样本专题索引
tags: [pokopia, 2-0-1, samples, hex]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 真实样本｜从字节到导出结果

本目录只记录可在仓库源文件中定位的字节、样本记录与源码。**结构证明**、**资源关联证明**、**游戏语义证明**分开保存；不能将分析脚本可读取的字段直接命名为游戏的官方枚举。

| 样本 | 已核验内容 | 不应推断 |
| --- | --- | --- |
| [[01-Item-00983-Real-Hex]] | 64 字节头、68 字节记录、物品 ID 6 名称索引 | 材料类型、背包上限、最大堆叠 |
| [[02-Localization-04645-Real-Hex]] | 3,001×32 的日语名称表及相对指针 | 所有文本均是物品名称 |
| [[03-TEXINFO-108-Byte-Real-Hex]] | 108 字节 TEXINFO 单记录，真实 UV 浮点数 | 未建立引用关系的 G1T 或像素身份 |
| [[04-M7-Nine-Language-Trace]] | 2350～2358 九语言单条记录的原生偏移与控制标签 | 场景、任务、角色、建筑的外键 |

原始游戏二进制文件不复制进 Markdown；用短 Hex 摘录、源路径、SHA-256 或 Git Blob SHA 和复现命令代替。此轮 Hex 来自当前分支 GitHub 文件的实际读取；**未在用户本地完整运行 ROM 解包**。

## 定位规则

- 仓库根目录作为 Obsidian Vault；条目的路径按仓库根目录写。
- SHA-256：针对源文件字节的哈希；Git blob SHA：Git 对 blob 对象的哈希，二者**不可混用**。
- 十六进制的偏移默认以文件开头为基准；如写“记录内 +0x22”，需明确记录起点。
- 对应测试和质量门禁见 [[docs/2.0.1/Technical/Validation/README|Validation 验收索引]]。
- 结构原理见 [[docs/2.0.1/Technical/Formats/README|Formats]]，操作入口见 [[docs/2.0.1/Technical/Workflows/README|Workflows]]。

[返回技术首页](../README.md)
