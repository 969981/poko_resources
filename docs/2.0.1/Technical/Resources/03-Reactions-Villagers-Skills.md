---
title: 表情村民技能参考文件位置及二进制ID映射
tags: [pokopia, resources, reaction, villagers, skills]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 表情 / 村民 / 技能：图片与多语言 ID 对账

**重要**：下列 PNG 和九语言文本来自固定 [PokoHex](https://github.com/969981/PokoHex/tree/c71d2b73fb9d8cfe99c1067e6bfadfd19f60bf78) 提交，并非已证明的 2.0.1 原生 TEXINFO/G1T 路径。导入器：[import_pokohex_extra.py](../../../../Scripts/resources/import_pokohex_extra.py)。

| 类别 | 目录（在 `UnPack/2.0.1/Resources/` 内） | CSV | PokoHex 原始来源 |
| --- | --- | --- | --- |
| 表情 | `Reactions/Icons/reaction_XXXX.png`、`Reactions/Text/` | `reaction_catalog.csv` | `PokoHex/Resources/Reaction/` |
| 村民 | `Villagers/Icons/villager_XXXX.png`、`Villagers/Text/` | `villager_catalog.csv` | `PokoHex/Resources/Villager/` |
| 技能 | `Skills/Icons/skill_XXXX.png`、`Skills/Text/` | `skill_catalog.csv` | `PokoHex/Resources/Skill/` |

九语言源文本：`PokoHex.Core/Resources/text/<lang>/text_{reaction,villager,skill}_<lang>.txt`，导入到本仓库每类的 `Text/`。各类还有 `pokohex_icon_sources.csv`，保留原始路径、图像 SHA。

### 表情：ID 通常直接对应图片文件名（参考数据规则）

报告：128 个 ID 槽、47 个有名称槽、47 张图片。样例 `reaction_id=6`，Celebrate/“太好了～！”，CSV 对应 `Reactions/Icons/reaction_0006.png`。ID 为空的行不删除。

### 技能：参考数据用独立的公开/轮盘标记

报告：64 槽、11 个有名称槽、10 张图片。样例 ID 1 Leafage/树叶 → `Skills/Icons/skill_0001.png`，`is_public=1`。ID 7 有名称但标 `is_public=0`，并无独立 PNG，不要当成当前公开技能的原生证明。

### 村民：**villager_id != portrait_id**

PokoHex 原始 `PokoHex.Core/Resources/byte/villager_portrait.bin` 为 **2,100 bytes** = 1,050 个 `uint16 little-endian`。某 ID 的值在文件偏移 `2 * villager_id`，决定要用 `villager_<portrait_id>.png`，而非使用村民 ID。

已直接读取的原始例子：

```text
villager_id = 49（Ivysaur / 妙蛙草）
map offset = 49 * 2 = 98 = 0x62
raw bytes = 03 00
portrait_id = 0x0003 = 3
PNG = Villagers/Icons/villager_0003.png
```

另例：ID 43 Voltorb/霹雳电球 → portrait_id 69 → `villager_0069.png`。

[来源与覆盖报告](../../../../UnPack/2.0.1/Resources/SOURCE_AND_COVERAGE.json)：村民 1,050 ID 槽、402 个有名称、378 张参考 PNG、374 个实际被使用的肖像 ID；不宜删除未引用的 4 张头像。游戏原生村民→资源 Hash、物种 ID 等关联**尚未完成**。

### 重建参考图（导入，不是 G1T 解码）

```powershell
git clone https://github.com/969981/PokoHex.git _work/PokoHex
git -C _work/PokoHex checkout c71d2b73fb9d8cfe99c1067e6bfadfd19f60bf78
python -m Scripts.resources.import_pokohex_extra --source _work/PokoHex --dest _work/PokoHex-resources
```

如需 **2.0.1 原始图像位置**，必须回到 [TEXINFO 其他纹理索引](../../../../UnPack/2.0.1/Resources/Textures/Indexes/native_misc_texture_index.csv)，查纹理名称、对象引用与 PNG 相似性，并建立游戏实际消费者关联。目前不能凭固定参考图片捏造原生路径。
