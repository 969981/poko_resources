---
title: 纹理提取与 PNG 转换
tags: [pokopia, texinfo, g1t, png, swizzle]
updated: 2026-11-05
---
# 原生纹理：TEXINFO → KIDSOBJDB → G1T → PNG

## 数据流与边界

1. 从解包 `*.texinfo` 取得纹理名、`record_index`、层号和四顶点 UV。
2. 用 KIDSOBJDB 索引里的确切 Hash 边匹配原版 `*.g1t`，保留源完整路径及两个 Hash。
3. 校验 G1T 签名 `GT1G0600`、`platform=0x18`、条目大小/格式；按 Ounce 特定布局做 swizzle 还原。
4. 对原图按 **原始 TEXINFO UV** 裁切；编码 PNG、记录长宽、透明度、SHA；对照参考图像及游戏画面。
5. **身份映射单独进行**：纹理名不是游戏物品 ID/宝可梦物种 ID 的自动证明。

原始主图集位于：
`UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/`。

- G1T：`root_038147_a0ce9914.g1t`。
- TEXINFO：`root_042753_b4b1fe49.texinfo`。
- 源索引：`UnPack/2.0.1/Resources/Textures/Indexes/item_atlas_1333_uv.csv`。

## 环境和命令

```bash
python -m pip install "Pillow>=11,<13"
python -m unittest discover -s tests -p "test_g1t_to_png.py" -v
# 解码器支持显式输入与布局选择；限量小样本
python -m Scripts.resources.g1t_to_png --help
python -m Scripts.resources.g1t_to_png --input UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native --layouts ounce2,ounce8,ounce16 --max-files 5
# 已经过原生证据约束的专用批量导出
python -m Scripts.resources.export_native_item_atlas
python -m Scripts.resources.export_native_pokemon_icons
python -m Scripts.resources.audit_native_pokemon_identity
# UI/材质纹理按批次执行，索引与数量必须对账
python -m Scripts.resources.export_native_misc_batches --batch 0 --batch-size 240
```

`g1t_to_png` 是通用候选解码器；将多个布局都输出不等于已判断正确。专用导出器采用源格式约束和经过对照的布局。输出路径及脚本参数仍以源码 `--help` 为准。

## 已有可复核批次

| 类别 | 当前原生输出 | 核验范围 |
| --- | --- | --- |
| 主道具双层图集 | 1,333 张，72×72，`ounce16` | 两层 BC7 2048×2048，727/606 |
| 第二道具图集 | 272 张 | 保留同 ID 的版本歧义 |
| 混合道具图集 | 14 张 | 13 BC7 + 1 BGRA |
| 宝可梦图标 | 609 张 | SHA/UV/G1T Hash 已关联；**物种 ID 0 条原生证明** |
| 非道具 UI/场景/素材 | 3,930 张（17 批） | 5 张全透明保留；另 418 条未唯一定位 |

主要原生资源账本：
- `Resources/Items/Native_2.0.1/native_icon_complete_catalog.csv`（物品图标/源键）。
- `Resources/Pokemon/NativeCandidates/pokemon_native_manifest.csv`（宝可梦纹理候选）。
- `Resources/Pokemon/pokemon_identity_crosswalk.csv`（身份待证）。
- `Resources/Textures/Indexes/native_misc_png_catalog.csv`（UI/素材批量 PNG）。
以上 `Resources/` 均指 `UnPack/2.0.1/Resources/`。

比较 PokoHex 图标只能标注“参考相似”，不能证明每像素一致。5 张全透明 PNG 也必须保留在审计中，不静默丢掉。不要覆盖 `Resources/Items/Icons/` 中来自第三方的原始图片。

深入细节：[原版 0x18 纹理结构与实验](../M5_NATIVE_TEXTURE_PIPELINE.md)、[[08-Evidence-And-Open-Questions]]。