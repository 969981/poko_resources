---
title: 原生文件格式专题索引
tags: [pokopia, 2-0-1, formats, binary]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---
# 文件格式专题｜原生字节与解析入口

> 本目录专门记录 **格式结构**；使用流程见 [[../Workflows/README|操作流程索引]]，源代码仍以仓库里的实际实现为准。不要用“能解码”替代“已解释游戏语义”。

| 文件 | 主要内容 | 证据层次 |
| --- | --- | --- |
| [[01-LINKDATA-IDX-BIN]] | IDX 定长记录、BIN 对齐、压缩 chunk | 代码与真实样本结构 |
| [[02-RDB-RDX-FDATA-IDRK]] | RDB、RDX、FDATA、IDRK、两种 footer | 已实现的结构 + 未支持项 |
| [[03-KIDSOBJDB-IDOK-RDOK]] | 属性头、类型表、RDOK 未解语义 | 固定宽度读取成立 |
| [[04-TEXINFO-G1T]] | 纹理表、UV、G1T header、Ounce 图片 | 部分图集闭合 |
| [[05-Native-Item-00983]] | 4,600 × 68 物品原始记录 | 原始字段可读；分类未证 |
| [[06-Native-Text-Tables]] | 原生 UTF-8 索引与九语言 | 物品名已验、外键未证 |

GitHub 浏览入口：[技术知识库首页](../README.md)。格式研究如发现反例，先保存失败样本、错误代码、脚本提交，再修正文档。
