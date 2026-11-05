---
title: 证据等级、反证与待研究项目
tags: [pokopia, verification, research-status]
updated: 2026-11-05
---
# 已验证、候选、反证、未完成

## 证据等级

- **E0**：仅文件名或扩展名猜测。
- **E1**：原始路径、字节数和 SHA 可核验。
- **E2**：索引与偏移结构通过边界和样本校验。
- **E3**：按原始字节可提取/恢复格式。
- **E4**：字段/资源关系经过独立原始数据与代码或使用者双向测试。
- **E5**：端到端解码或渲染可复现，原始输出与游戏画面/可靠基准留痕。

具体资源仍要分别记录 `SOURCE_EXISTS`、`INDEX_EDGE`、`PNG_DECODED`、`REFERENCE_SIMILAR`、`NATIVE_ID_VERIFIED`、`GAME_VISIBLE_VERIFIED`，不能凭 E5 PNG 推出游戏身份已验证。

## 重要反证：OpenSSL NID 983 ≠ 原生物品表编号

[M20 原始证据](../M20_ITEM983_CACHE_ORIGIN.md)已确认在 `main` 代码中看到的 `mov w0,#983 → 0x1445E30 → 0x14718F0 → 0x36D54C8` 属于 **OpenSSL GOST 加密对象 NID 983 查询链**，并非 `00983.bin` 加载器。两者数字相同不能串联。不要再沿这个调用链给材料字段背书。

## 仍未闭合的关键问题

| 主题 | 已有真证据 | 仍需取得 |
| --- | --- | --- |
| 宝可梦物种 ID | 609 TEXINFO/G1T 候选、KIDSOBJDB Hash；M17/M19 对 603 个不同纹理对象追到 typed OID 引用 | 原生 `species_id`/形态字段的直接来源、对象消费者 → 相同纹理 Hash，游戏实例验证；现 `verified=0` |
| 材料枚举 | `00983.bin` 64 + 4,600×68；`+0x26/+0x39/+0x3A` 消费者，registry `0xC7` / vtable `+0x30` | 返回对象 `+8` 追溯回真实原始记录以及明确分类用途/枚举名称 |
| 单组/持有上限 | 数据表和代码候选、数值范围 | 逐物品上限或游戏规则调用点；不能由单字节容量推断 255 是游戏堆叠上限 |
| 剧情/任务文本外键 | 九语言文本表结构与候选，部分 RNK/对象 Hash | 恢复缺失 `_RNK0000` 原始来源及脚本/对象实际消费 `table_id`、`text_id` |
| UI/材质剩余纹理 | 3,930 张原生 PNG 已批次输出 | 368 条原始 G1T 路径不可唯一找到、50 条 Hash 歧义；需逐项核验和真实画面对照 |

## 新笔记须附带的最小证据

原始源路径及 SHA、样本 offset/长度/端序、精确引用脚本和命令、输出文件 SHA、成功/失败样本、否证、关联等级、尚未完成的外键。若无法确认，字段留空或填 `UNKNOWN`；对过往错误结论留**勘误**而不悄悄覆写审计历史。

研究入口：[M17–M19 物种/物品状态](../M17_M19_NATIVE_ID_AND_ITEM_ENUM_STATUS.md)、[M9 外键及 RNK](../M9_POKEMON_ITEM_IDENTITIES.md)、[[09-Research-Template]]。