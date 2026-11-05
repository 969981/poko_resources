---
title: 原始资源位置和导出产物对应表
aliases: [原始文本文件位置, 资源路径映射, 来源追溯]
tags: [pokopia, provenance, localization, textures, resources]
game_version: "2.0.1"
status: PARTIAL_MAPPING
updated: 2026-11-05
---
# 从输出文件反查原始 RomFS / LINKDATA / FDATA

> 本表中的所有相对路径从仓库根目录开始。下面的 `Resources/` 专指 `UnPack/2.0.1/Resources/`；“位置已知”不等于“游戏逻辑语义已确认”。

## 已确认的关键源文件与位置

| 数据目标 | 原始/解包中间层 | 已有消费或索引 | 关联状态 |
| --- | --- | --- | --- |
| 4,600 条物品原始结构 | `UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin` | `Resources/Items/Native_2.0.1/native_item_raw_fields.csv` | 68 字节原始记录已读；分类、数量上限仍待调用链证明 |
| 日文物品名称 | 同目录 `04645.bin` | `Resources/Items/Text/text_item_jp.txt` | 九语言名称校验的一部分 |
| 英文物品名称 | `04646.bin` | `text_item_en.txt` | 同上 |
| 法文物品名称 | `04647.bin` | `text_item_fr.txt` | 同上 |
| 意大利文物品名称 | `04648.bin` | `text_item_it.txt` | 同上 |
| 德文物品名称 | `04649.bin` | `text_item_de.txt` | 同上 |
| 西班牙文物品名称 | `04650.bin` | `text_item_es.txt` | 同上 |
| 繁体中文物品名称 | `04651.bin` | `text_item_zht.txt` | 同上 |
| 韩文物品名称 | `04652.bin` | `text_item_ko.txt` | 同上 |
| 简体中文物品名称 | `04653.bin` | `text_item_zhs.txt` | 同上 |
| 主道具纹理图集 | `UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/root_038147_a0ce9914.g1t` | `Textures/Indexes/item_atlas_1333_uv.csv` | 原生 G1T 已关联 |
| 主道具名称和 UV | 同目录 `root_042753_b4b1fe49.texinfo` | `Items/Native_2.0.1/native_icon_complete_catalog.csv` | 1,333 条主图集精确裁切 |
| 宝可梦图标候选 | 同一 FDATA 的原生 `*.g1t` / `*.texinfo` 关联文件 | `Pokemon/pokemon_texture_index.csv`、`Pokemon/NativeCandidates/pokemon_native_manifest.csv` | 609 条图像来源；原生 species ID 尚未绑定 |
| 其他 UI / 素材 / 场景图 | 原生 KIDSOBJDB Hash → TEXINFO/G1T | `Textures/Indexes/native_misc_texture_index.csv`、`native_misc_png_catalog.csv` | 3,930 条可唯一定位，其他仍有缺失/歧义 |
| 剧情、任务、建筑文本 | LINKDATA 解码的其他候选 `NNNNN.bin` | `Localization/M7/`、`Localization/M8/` | 九语表内部 ID 可追；具体消费外键仍 UNKNOWN |

上表中的 `text_item_*.txt` 完整路径为 `UnPack/2.0.1/Resources/Items/Text/` 下相应文件。九语言表号来自当前已验证的物品名称链路，**不要扩展断言为完整九语言剧情库**。

## 反查一张图片的证据链

1. 在原生清单中找到 `png_path` 与 `png_sha256`。
2. 查 `texinfo_hash`、`g1t_hash`、原始路径、`texinfo_record_index`、`texture_layer`、`uv_rect`。
3. 回到 `UnPack/2.0.1/romfs/...fdata/native/` 定位真实 G1T/TEXINFO，校验 SHA、格式和 UV。
4. 查 KIDSOBJDB/原生对象引用。**纹理来源证据**与**官方 item_id/species_id 身份证据**分两列，不以文件名数字冒充游戏物种 ID。
5. 对照游戏画面属于另一个验收阶段，输出 `GAME_VISIBLE_VERIFIED` 前需留样本证据。

道具出现同一个 `item_id` 对应多个来源时保留原始变体（例如当前已审计的 1677、1764、1765、2742），不静默覆盖。

## 反查一条文本

1. 取得 `language`、`text_id` 与原始 `entry_index`，优先查看 M7 原始偏移、字段与控制符。
2. 查对应 `LD_C0_R.BIN/decoded/NNNNN.bin` 的 SHA 和字节偏移。
3. 对物品名称按零基 `item_id` 行号读取 `text_item_<lang>.txt`，**保留空行**；通过 `validation.json` 与 `00983.bin +0x22` 对账。
4. 若想标“剧情/建筑/任务”，必须继续取得脚本/对象字段 → `table_id` → `text_id` 的真实外键；暂时只写 `UNKNOWN`。

## 建议保留的统一溯源字段

`game_version, source_romfs_path, source_archive_path, decoded_path, source_sha256, entry_index, byte_offset, byte_length, object_hash, texinfo_hash, g1t_hash, texture_layer, uv_rect, layout, output_path, output_sha256, language, raw_text_id, native_item_id_verified, native_species_id_verified, evidence_grade, status, verifier`

这是**建议的新衍生账本字段**，不保证所有现有 CSV 已包含全部列。既有字段以实际 header 为准；可将未知值留空，并注明原因。

参考 [[01-Source-Layout]]、[[04-Texture-Pipeline]]、[[05-Localization]]、[[07-Data-Usage]] 和 [资源 README](../../../UnPack/2.0.1/Resources/README.md)。
