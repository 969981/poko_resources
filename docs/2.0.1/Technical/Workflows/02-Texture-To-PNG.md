---
title: 纹理从原生文件转换至PNG
tags: [pokopia, 2-0-1, texture, png, pipeline]
game_version: "2.0.1"
status: ACTIVE
updated: 2026-11-05
---
# TEXINFO / G1T → PNG：两条独立流程

前提：先从 [[01-Restore-And-Decode]] 得到含 `native/*.g1t` 和 `native/*.texinfo` 的真实解包目录。

## 路线 A：通用布局候选（不会自动证明正确）

```powershell
python -m pip install "Pillow>=11,<13"
python -m unittest discover -s tests -p "test_g1t_to_png.py" -v
python -m Scripts.resources.g1t_to_png --input UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native --layouts ounce2,ounce8,ounce16 --max-files 5 --dest _work/texture-candidates
```

按 CSV 中 `status, reason, format, layout, width, height, png_sha256` 检查；出现条纹、错位、黑块时优先复核 **format / swizzle / row pitch / mip / UV**，不要通过重命名图片“修复”对应关系。

## 路线 B：已针对主道具图集校验的导出器

```powershell
python -m Scripts.resources.export_native_item_atlas
python -m Scripts.resources.reconcile_native_item_icons
```

默认输入来自同一 `0x00011c54.fdata/native` 下两份主图集 G1T/TEXINFO、`Resources/Textures/Indexes/item_atlas_1333_uv.csv`，结果保存到 `Resources/Items/Native_2.0.1/`。与 `Resources/Items/Icons/` 中第三方参考图分离。

## 宝可梦、UI 和素材

```powershell
python -m Scripts.resources.export_native_pokemon_icons
python -m Scripts.resources.export_native_misc_batches --batch 0 --batch-size 240
python -m Scripts.resources.reconcile_native_misc_batches
```

对每张 PNG 保存双源路径、SHA、layer、UV、尺寸、实际选用布局与证据等级；609 条宝可梦纹理记录是**候选来源**，不得据此自动填原生物种 ID。

参见 [[docs/2.0.1/Technical/Formats/04-TEXINFO-G1T]] 和 [[13-Resource-Provenance-Map]]。
