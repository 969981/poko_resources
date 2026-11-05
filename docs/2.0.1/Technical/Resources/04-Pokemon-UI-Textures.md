---
title: 宝可梦以及UI场景其他图像原始来源
tags: [pokopia, resources, pokemon, ui, texture]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# Pokémon / UI / 场景：原始 TEXINFO → G1T → PNG

## Pokémon 图标

[原生汇总](../../../../UnPack/2.0.1/Resources/Pokemon/README.md)：609 条原生 TEXINFO 候选（普通 `icon_poke_` 301，`icon_poke_uni_` 308），603 个不同名称；609 张已导出 PNG，其中 29 张由等值解码别名还原源 G1T。609/609 有 KIDSOBJDB Hash 关联，**原生物种 ID 映射 0 条已证**。

- 原生对应关系：`UnPack/2.0.1/Resources/Pokemon/pokemon_texture_index.csv`。
- PNG 文件：`UnPack/2.0.1/Resources/Pokemon/NativeCandidates/{pokemon,pokemon_uni}/`。
- manifest：`Pokemon/NativeCandidates/pokemon_native_manifest.csv`。
- Hash/对象图：`Pokemon/pokemon_identity_crosswalk.csv`。
- 导出：`python -m Scripts.resources.export_native_pokemon_icons`，校验：`python -m Scripts.resources.audit_native_pokemon_identity`。

**真实配对示例**（经本轮字节读取）：原生目录
`UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/`

- `root_000147_00a2d79b.texinfo`：`icon_poke_uni_0180_00_00_00`，layer 0，UV 0..0.75。
- `root_017070_47b4eb66.g1t`：4148 bytes、format 0x66 BC7、64×64、platform 0x18；通过 Ounce2 → UV 得到 48×48 PNG。
- 输出：`Pokemon/NativeCandidates/pokemon_uni/icon_poke_uni_0180_00_00_00__00a2d79b__47b4eb66.png`。

**名字里的 0180 不等于已证明的官方 species_id。** 六条同名不同 Hash 不覆盖。

## UI、地图、场景、纹饰及其他素材

- [TEXINFO 名称索引](../../../../UnPack/2.0.1/Resources/Textures/texinfo_names.csv)
- [TEXINFO / G1T / KIDSOBJDB 索引边](../../../../UnPack/2.0.1/Resources/Textures/Indexes/native_misc_texture_index.csv)
- [实际 PNG 路径与 SHA](../../../../UnPack/2.0.1/Resources/Textures/Indexes/native_misc_png_catalog.csv)
- 输出：`UnPack/2.0.1/Resources/Textures/MiscNativeBatches/batch_00...batch_16/`，各批 `Images/` 与 `batch_audit.json`。

[批量验收汇总](../../../../UnPack/2.0.1/Resources/Textures/Indexes/native_misc_png_summary.json)：7,566 条 TEXINFO，其他类别 4,348 条，其中 3,930 条建立唯一原生 G1T 索引；17 批 3,930 条都生成 PNG 候选，**3,925 条待游戏画面复验，5 条透明需审查**。不能因为文件名有 `material`、`icon`、`shop`、`still` 便写入游戏官方材料分类。

| 文件名推测组 | 记录数 | 证据等级 |
| --- | ---: | --- |
| `ui_icon_name_candidate` | 1579 | 名字启发式 |
| `ui_gameplay_name_candidate` | 1172 | 名字启发式 |
| `material_name_candidate` | 5 | 名字启发式，不代表 5 种材料 |
| `other_native_sprite_name` | 1592 | 其他 |

另外 368 条找不到唯一 G1T 物理源、50 条没有唯一对象索引边，不能以“图片不存在”处理。详细导出参见 [[05-Image-Export-Guide]]，原始十六进制 G1T 头参见 [[06-Hex-Format-And-Lookup]]。
