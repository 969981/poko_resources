---
title: 资源原始位置与导出百科
tags: [pokopia, resources, obsidian, index]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# Resources：原生位置、路径、图片导出和内部字段

本目录在 Obsidian 中从技术知识库 [[docs/2.0.1/Technical/README|主页]] 进入。**所有路径相对于仓库根目录**；原生 2.0.1 文件、从原生解包而来的 PNG、PokoHex 固定参考资源必须分开标记。

| 类别 | 文档 | 当前来源 |
| --- | --- | --- |
| 原始镜像/解包/输出树 | [[01-Original-Path-Map]] | 原生 |
| 物品、食物、材料、建筑、家具 | [[02-Items-And-Native-Kinds]] | 00983.bin + G1T；分类正式枚举未证 |
| 表情 / 技能 / 村民头像 | [[03-Reactions-Villagers-Skills]] | PokoHex 固定参考，非已确认的原生图源 |
| 宝可梦、UI、场景、杂项图 | [[04-Pokemon-UI-Textures]] | 原生 TEXINFO/G1T 候选 |
| G1T→PNG 与导入脚本 | [[05-Image-Export-Guide]] | 复现手册 |
| 真正的十六进制值与内部字段 | [[06-Hex-Format-And-Lookup]] | 实际源字节 |
| 九语言与查询示例 | [[07-Languages-And-Resource-Search]] | 原生/参考分开 |

**证据分级**：可读取原生字节 ≠ 建立纹理 Hash 索引 ≠ 生成 PNG ≠ 游戏内真实显示 ≠ ID / 类别含义被原生代码证明。物品 +0x26 的官方类别、逐物品堆叠上限、原生村民/表情 ID 和宝可梦物种 ID 的直接关联仍待补证。

原有 [Formats](../Formats/README.md)、[Samples](../Samples/README.md)、[Validation](../Validation/README.md) 和 [Resources 总账](../../../../UnPack/2.0.1/Resources/README.md) 仍适用。

## M23：物品分类证据链下一步

- [[08-M23-Native-Category-Proof]] · [GitHub M23 手册](08-M23-Native-Category-Proof.md)：GDB 动态读取 V1/V2 两级虚表目标，并把现场完整 68 字节与原版 00983.bin 逐项对账；尚无真实运行时验收结果，分类官方枚举未证明。

## M24：消费者静态矩阵与分场景验收

- [[09-M24-Consumer-Context-And-Acceptance]] · [GitHub M24 文档](09-M24-Consumer-Context-And-Acceptance.md)：已用原版 M12/M20 结果建立 17 个直接查询调用点的字段访问矩阵；记录/虚表的真实游戏运行时验证以及背包、制作、建造语义仍需 GDB 采集。
