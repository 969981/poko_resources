---
title: Pokopia 2.0.1 M7.1 未匹配文本家族与九语言候选
aliases: [M7.1 Text Families, 九语言未匹配文本证据]
tags: [pokopia, m7, native-text, localization, provenance, hypotheses]
updated: 2026-11-05
---

# M7.1 — 从 965 张未知表中整理结构候选

**证据边界：不是新的九语言正式映射，也没有证实剧情、任务、场景、物种 ID 或脚本调用者。以下仅为原生数据结构与内容审查线索。**

## 本轮执行

- 入口：Scripts/resources/triage_unlinked_text_families.py
- 测试：tests/test_unlinked_text_families.py
- [M7.1 原生 CI 成功记录 #42027776346](https://github.com/969981/poko_resources/actions/runs/42027776346)
- 来源：Pokopia 2.0.1 / UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/
- 原生 SHA-256、长度、解析 count、stride、非空位图、flags：**983/983 逐文件校验通过**。
- M8 正向对照：02332–02340 Reactions、04942–04950 Skills，共 18 张，有独立固定版本解析器证据。

## 983 张的互斥划分

| 状态 | 九文件候选位置 | 涉及原生表 |
|---|---:|---:|
| 恰好九张连续 + 多语言文字脚本证据（仍属候选） | 22 | 198 |
| 长于九张连续、无法唯一切分 | 61 | 549 |
| 恰好九张但文本过少 | 18 | 162 |
| 不构成完整九张分组的表 | — | 56 |
| 已有 M8 原生角色表证据的对照组 | 2 | 18 |
| **合计** | **103** | **983** |

因此 M8 以外仍然有 **965 张未知身份表**，其中 **198 张（22 组）是优先调查对象**。

输出：UnPack/2.0.1/Resources/Localization/TextFamilies/

- native_text_families_report.json：全量统计、证据边界和 M8 正向对照。
- unlinked_native_shape_runs.csv：107 个最大连续结构区间；flags 差异仍逐源保留。
- nine_language_hypotheses_NOT_VERIFIED.csv：103 个分组位置、原始 SHA-256、文字脚本观察值、flags 哈希种数及候选等级。
- unsegmented_native_text_tables.csv：余下 56 个无法构成完整九文件分组的原生文件。

## 22 个唯一九文件位置（仅候选）

起始编号对应的原生文件为 start 到 start+8。下列“内容方向”仅来自英文等文本样本，**不是官方字段、资源类型、游戏对象或已验证外键**。

| 起始 Entry | 记录数 | flags 哈希种数 | 文本内容审查线索 |
|---|---:|---:|---|
| 02125 | 16 | 2 | 干燥/潮湿等环境状态词 |
| 02134 | 16 | 2 | 明暗词 |
| 02152 | 64 | 4 | 材质、花草、水等描述词 |
| 02161 | 64 | 5 | 另一套相似的描述词 |
| 02170 | 51 | 5 | 包与佩饰等名称 |
| 02251 | 51 | 3 | 人物套装名称 |
| 02260 | 1024 | 5 | 宝可梦名字（物种 ID 尚未证明） |
| 04141 | 16 | 2 | 摄影滤镜、画面效果词 |
| 04150 | 64 | 2 | 重复短词，仍需研究 |
| 04555 | 31 | 3 | 发型名称 |
| 04564 | 51 | 5 | 帽子与头饰名称 |
| 04672 | 51 | 2 | 裤装名称 |
| 04870 | 64 | 5 | 视觉/特效名称 |
| 04933 | 1024 | 5 | 另一套宝可梦名字 |
| 04960 | 32 | 5 | 宝可梦属性类型名称 |
| 04996 | 6 | 5 | 等级或评价用词 |
| 05005 | 13 | 3 | 功能/舒适度分类词 |
| 05050 | 51 | 5 | 鞋子名称 |
| 05077 | 64 | 5 | 建造、放置、种植等动作词 |
| 05086 | 32 | 5 | 地名、区域名称 |
| 05140 | 5 | 2 | 层级称谓 |
| 05212 | 51 | 4 | 上装名称 |

宝可梦名称表 02260 与 04933 的文本 ID 不能直接当作物种 ID；同仓库 Pokemon/pokemon_identity_summary.json 的 species_id_verified_count 仍为 0。05077 出现 build 等词，也不能因此直接定为已经证明 Buildings 调用的文本表。

## 为什么 M7 严格匹配漏掉了它们？

旧 M7 要求记录数量、8/32 字节布局、非空记录位图，以及 8 字节布局中的所有原始 flags 序列都完全一致。M7.1 保留前三项，在候选发现时放宽 flags，并检查可能的九语言文字脚本位置。22 个唯一九文件候选全部存在 flags 哈希差异；这与 M8 已验证反应动作与技能表的现象相似。

**这种相似性只能提高调查优先级。** 它既不是 locale 的原生调用关系，也不能证明某些词属于游戏的哪一个字段。

对于 18、27、36、54、171 等长区间，不把每九张的切分位置当作已证实边界，仍为 AMBIGUOUS_MULTI_GROUP_RUN_NOT_VERIFIED。

## 下一阶段闭合的来源证据

1. 优先复查 02260/04933 名称表、02152/02161/05005 特征词、05077 动作词、05086 区域名等对应的游戏原生消费者。
2. 从真实 ExeFS、bfbs、Lua 或原生资源读取路径找到具体 LINKDATA entry 的加载者，追踪**同一对象中有类型的行 ID 字段**、原始字节偏移和来源 Hash。
3. 按照 caller → resource table → row ID → 语言值的全链条与源字节复核，才可把候选升级为已证明关系。
4. M9 目前 5,365 条类型化资源外键已验证，但不代表上述 22 组新增了脚本调用。正式字段分类未变化，未知仍是 UNKNOWN。

## 重建

~~~bash
python -m unittest discover -s tests -p 'test_unlinked_text_families.py' -v
python Scripts/resources/triage_unlinked_text_families.py
~~~

相关文档：[[16-Native-Text-Exports]]、[[17-Unlinked-Native-Text-Exports]]，以及 Resources/Localization/M9/README.md。
