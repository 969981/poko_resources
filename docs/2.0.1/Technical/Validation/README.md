---
title: 解包文档与资源验收索引
tags: [pokopia, 2-0-1, validation, qa]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 验收与回归｜证据门禁

本目录是“格式读取成功”到“图片或游戏文本可信”的检查层，不是新的解码器。

| 文档 | 使用场景 |
| --- | --- |
| [[01-Byte-To-Output-Checklist]] | 每个原始资源到 PNG/CSV/JSON/SQLite 的追溯字段与验收门禁 |
| [[02-Regression-Test-Commands]] | 针对 LINKDATA、RDB、G1T、M7、00983 的既有测试入口与命令 |
| [[03-Source-Verification-Matrix]] | 已提交的测试报告、当前结论与尚待证明的身份/外键 |

审核规则：

1. **格式与边界**：原始 magic / version / count / offset / record size 不匹配时失败，不产出“已解析成功”记录。
2. **来源与转换**：保留完整原始文件路径、索引条目、源 SHA-256、代码入口、参数、输出路径和输出哈希。
3. **资源与语义**：解析得到记录，不等于已知游戏内 ID；PNG 生成成功不等于 sprite 来源或视觉完全确认。
4. **回归**：把可用的既有测试与真实资源检查分开列出，记录实际执行日期和结果。文档中的“仓库历史报告”不是此次会话新跑出的测试。

本轮仅对 GitHub 版本中的部分真实二进制头/记录做了字节级读取，并核对既有测试源码和历史 JSON/CSV。**没有在本地运行整套 ROM 还原或所有 Python 单元测试**。

[返回技术首页](../README.md)
