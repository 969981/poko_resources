---
title: 原生解包与转换操作流程
tags: [pokopia, 2-0-1, workflow, runbook]
game_version: "2.0.1"
status: ACTIVE
updated: 2026-11-05
---
# 操作流程索引：按顺序运行

| 流程 | 输入 → 输出 | 注意 |
| --- | --- | --- |
| [[01-Restore-And-Decode]] | 分卷 → BIN / FDATA → raw/decoded | 保留元数据和缺失状态 |
| [[02-Texture-To-PNG]] | TEXINFO + G1T → PNG / manifest | 布局/UV/身份分别验证 |
| [[03-Localization-To-CSV]] | LINKDATA → 九语言文本 / 表索引 | 不重排零基行号 |

全部命令默认在仓库根目录 Windows PowerShell 下执行；脚本参数与最新源码不符时优先运行 `python -m <module> --help`。更多旧版完整配方：[[12-Reproducible-Recipes]]。
