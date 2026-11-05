# M21 — Pokopia 2.0.1 原生表情、技能与村民头像证据链

## 目标与来源

本阶段只接受仓库已导出的 **2.0.1 ROMFS 原始 TEXINFO/G1T→PNG**，而不直接把 `PokoHex` 图标当成原生文件。PokoHex（固定提交 `c71d2b73fb9d8cfe99c1067e6bfadfd19f60bf78`）只提供参考图及 ID/名称关联。

原始资源目录：

```text
UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/
  root_058132_f552e8cf.texinfo  # 原生 emote 与 skill 共同图集的 TEXINFO
  root_008846_24e5b69a.g1t      # 对应 BC7 / Ounce16 G1T
```

| 类别 | 原生纹理名与数量 | 现有原生 PNG | PokoHex 参考 PNG |
|---|---|---|---|
| 表情 | `icon_emote_001`～`icon_emote_040`，40 条 | `Textures/MiscNativeBatches/batch_14` 和 `batch_15` | `Reactions/Icons/`，47 张 |
| 技能 | `icon_skill_000`～`icon_skill_013`，14 条 | `Textures/MiscNativeBatches/batch_15` | `Skills/Icons/`，10 张 |
| 技能辅助遮罩 | `icon_skill_mask_000`～`013`，14 条 | `Textures/MiscNativeBatches/batch_15` | 没有等值前提 |
| 村民头像候选 | `icon_poke_*` / `icon_poke_uni_*` 等原始 609 条 | `Pokemon/NativeCandidates/` | `Villagers/Icons/`，378 张 |

注意：技能原生 `005`、`009`、`010` 的 PNG 为 4×4 全透明，不应以其名字推断为可用技能。详见 [原始透明候选复核](../../UnPack/2.0.1/Resources/Textures/Indexes/native_misc_transparent_review.md)。

### 核实过的逐图视觉样本

- `reaction_0006.png` 与原生 `icon_emote_001__f552e8cf__24e5b69a__r23.png` 的图案一致；
- `skill_0001.png` 与原生 `icon_skill_001__f552e8cf__24e5b69a__r362.png` 的图案一致；
- `villager_0019.png`（雷丘）与原生 `icon_poke_0026_00_00_00__8fe846b7__f7664882.png` 的图案一致。

这三个样本是 **人工视觉核对**，不能据此假定全部图片编号同序或像素一致。游戏人物 ID、PokoHex 肖像 ID、纹理名中的数字是不同的主键。

## 可复现导出和严格匹配

脚本：`Scripts/resources/export_native_aux_icons.py`

```bash
python -m pip install "Pillow>=11,<13"
python Scripts/resources/export_native_aux_icons.py
# 也可指定 --category Reactions / Skills / Villagers
```

脚本读取以下已有原生证据：

- `Textures/MiscNativeBatches/batch_14/misc_native_sample_manifest.csv` 和 `batch_15/...`；
- `Pokemon/NativeCandidates/pokemon_native_manifest.csv`；
- 各组 `pokohex_icon_sources.csv` 与 `{reaction,skill,villager}_catalog.csv`。

验证原生 PNG 与第三方 PNG 的 SHA256 文件字节；先比较 **宽高、可见 RGBA 像素 SHA256**（完全透明像素的 RGB 规范化为零）。如没有严格逐像素相同项，再对同尺寸图片的 **32×32、Alpha-aware 图像缩略图**计算归一化 MAE，并记录前两名距离。仅当第一名距离 ≤0.015、与第二名的距离差 ≥0.015 时，输出高区分度的视觉匹配**候选**；它不等于像素全同，更不等于原生游戏身份 ID 已验证。不按编号相等、名称相似或文件邻近关系直接赋 ID。

输出：

```text
UnPack/2.0.1/Resources/
  Reactions/Native_2.0.1/
    Icons/                     # 40 张原生 emote，保持原生名称+哈希+record
    native_icon_crosswalk.csv
    native_icon_summary.json
  Skills/Native_2.0.1/
    Icons/                     # 14 张原生 skill，包含 3 个透明占位候选
    native_icon_crosswalk.csv
    native_icon_summary.json
  Villagers/Native_2.0.1/
    Icons/                     # 像素全同或高区分度视觉候选的原生 pokemon 图
    native_icon_crosswalk.csv
    native_icon_summary.json
```

- `PIXEL_EXACT_UNIQUE`：有唯一可见 RGBA 像素相同的原生来源，可作为**图片同一性**证据。
- `PIXEL_EXACT_MULTIPLE_SOURCES`：多个不同原生来源像素相同，保留所有候选，不强行去重。
- `NO_PIXEL_EXACT_NATIVE`：在本轮 40/14/609 原生候选范围内没有逐像素同一项；不等于 ROMFS 不存在该图。

`reference_game_ids_from_pokohex` 属于第三方映射；即使像素匹配，也不能声称已经通过原生游戏物种/村民 ID 读取链确认。所有原始 G1T/TEXINFO 文件仍保持在原始 ROMFS 镜像路径下。

## 运行方式和验收

GitHub Actions：`.github/workflows/unpack-m21-native-aux-icons.yml`。工作流使用稀疏检出、PNG SHA256 检查、像素核对和独立 CSV/JSON 输出，并回写 `Native_2.0.1` 三组目录。工作流运行结果要以实际输出的 `native_icon_summary.json` 为准，不能凭前述候选数量宣称全部匹配完成。

后续：对未匹配的村民肖像，从 ROMFS KIDSOBJDB、原生角色形态/肖像索引与渲染调用链寻找附加纹理源；对未匹配的表情和技能从其它 TEXINFO 或图集页补查。强制保留差异清单，不用 PNG 文件名做虚假关联。

## 实际完成情况：2026-11-05 M21 原生导出

[GitHub Actions 成功运行 41965820438](https://github.com/969981/poko_resources/actions/runs/41965820438)，三类 `Native_2.0.1` 已通过 source-qualified PNG 和交叉引用校验并提交。

| 类别 | 第三方参考图 | 原生 PNG 索引范围 | 高区分度视觉关联 | 无可靠视觉关联 | RGBA 完全一致 |
|---|---:|---:|---:|---:|---:|
| Reactions | 47 | 40 | 40 | 7 | 0 |
| Skills | 10 | 14（其中 3 个透明占位） | 10 | 0 | 0 |
| Villagers | 378 | 609（普通 + uni + 特殊） | 290 | 88 | 0 |
| 合计 | 435 | 663 | 340 | 95 | 0 |

**严格性解释**：第三方参考图和原生 PNG 的肉眼画面高度一致，但其像素不是逐字节完全相同，故 `pixel_exact_matched_reference_icons=0`。高区分度匹配不是「相同 PNG」或「原生 ID 映射已证明」。`Native_2.0.1/Icons` 存储的是原版 G1T 解码 PNG，而不是来自 PokoHex 的复制品。

### 尚未关联的原生图追踪

- 7 个未匹配表情参考 ID：**83、84、85、86、87、93、95**。它们与现有 `icon_emote_001..040` 的最佳归一化视觉距离均为 0.13～0.17，属于本轮原生图集**没有相似原图候选**，不能强行编号映射。
- 88 个未匹配村民头像中，**9 项**已找到距离 ≤0.015 的近似候选，但第一、第二候选间距不足 0.015，暂不自动采用。这 9 个 PokoHex 肖像 ID 是 **16、18、96、98、218、220、296、297、298**；其中部分 `_nh` 原版纹理存在多个同类版本，必须进一步区分。
- 其余 **79 项**村民参考图与当前 609 张原生宝可梦纹理的最近候选距离大于 0.015。这意味着 **当前原生 609 范围内**没有可靠匹配，不证明完整 RomFS 中不存在这些图。

后续应扩展可能遗漏的独立头像图集、未解析/索引歧义的 TEXINFO/G1T，以及验证村民外观引用表。遇到同纹理不同原始记录、Alpha/颜色差异或特殊形态，必须保持来源 Hash 和候选列表，不按最接近者直接写实锤 ID。

## 后续 M22 原生追踪

已新增 [M22 村民头像 79 张缺失源与 9 张变体原生字段逐字节核验](M22_VILLAGER_NATIVE_SOURCE_AUDIT.md)。结果：79 张在原有 3,930 张非宝可梦原生图像中无新的高置信候选；9 张涉及 54 条原生 typed-object→纹理 Hash 引用，经源文件 SHA 与字段字节验证，但 game villager ID 语义仍未证明。原始缺失资源里 557 条 G1T、12 份 TEXINFO（最多 15 Sprite 记录）需分源补齐核对。
