---
title: TEXINFO/G1T/Ounce 图片格式
tags: [pokopia, 2-0-1, texinfo, g1t, texture]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---
# TEXINFO / G1T → RGBA → UV 裁切

原生样本目录：

`UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/`

道具主图集样本：

- `root_042753_b4b1fe49.texinfo`：已核验 1,333 条纹理记录；
- `root_038147_a0ce9914.g1t`：对应道具图集的原生纹理来源。

解析来源：[g1t_to_png.py](../../../../Scripts/resources/g1t_to_png.py)、[export_native_item_atlas.py](../../../../Scripts/resources/export_native_item_atlas.py)。

## 1. TEXINFO 字节结构

文件 = `u32_le count` + `count × 104`。第 n 个记录起始 `4 + n × 104`：

| 相对偏移 | 类型 | 含义 |
| --- | --- | --- |
| `+0x00` | 64 bytes ASCII | NUL 终止的名称 |
| `+0x40` | u32 | 原始 layer 字段 |
| `+0x44` | 8×f32 | 顺序为 `u0,v0,u1,v0b,u0b,v1,u1b,v1b` |
| `+0x64` | u32 | 尾字段，语义未知 |

UV 用四角检查是否为矩形、坐标是否在合法范围，不要在原生数据里提前整数化。仅 TEXINFO 名称并不能证明使用哪一份 G1T，需要文件关联证据。

## 2. G1T 头与偏移表

`GT1G0600` 为现有解析器要求的 8 字节签名。`+0x08` 开始四个 u32 little-endian：

| 偏移 | 字段 |
| --- | --- |
| `0x08` | 声明文件长度 |
| `0x0c` | offset table 起点 |
| `0x10` | texture_count |
| `0x14` | platform，Ounce 样本为 `0x18` |

偏移表含 `count` 个 u32，**每条纹理起点 = table 起点 + 相对 offset**。单张纹理前 8 字节含 `mip_sys`、`format`、`dxdy`、扩展头标志等；若存在扩展头，解析器从 `+8` 读 extra_size，并在满足最小头长时读扩展宽高。常见原生 `format=0x66` 为 BC7，`0x0A` 为 BGRA8888；其他格式须按实现与样本独立验收。

## 3. Swizzle、压缩与裁图

- Ounce `0x18` 的块排列不能与旧 Switch/GOB 假设直接等同。探索工具有 `ounce1/2/4/8/16/32` 候选；道具主图集专用导出器固定已核验的布局。
- 对 BC7：**先恢复块线性顺序，再封装 DDS 解码**，得到 RGBA；对 BGRA8888 走对应字节排列恢复。
- 使用 TEXINFO 原始 UV 指向的区域裁图；输出记录 layout、G1T/TEXINFO hash、record_index、layer、crop_box、PNG SHA。
- 纹理的存在 ≠ “该 sprite 名称中的数字就是宝可梦 species ID”；关联的证据单独保存。

## 4. 命令与产物

```powershell
python -m unittest discover -s tests -p "test_g1t_to_png.py" -v
python -m Scripts.resources.g1t_to_png --input UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native --layouts ounce2,ounce8,ounce16 --max-files 5 --dest _work/texture-preview
python -m Scripts.resources.export_native_item_atlas
python -m Scripts.resources.export_native_pokemon_icons
```

主图集的 UV 索引位于 `UnPack/2.0.1/Resources/Textures/Indexes/item_atlas_1333_uv.csv`，输出与旧 PokoHex 参考图必须隔离保存。宝可梦 609 条是**纹理索引条目**，不是经证明的 609 个原生物种。

相关：[[../Workflows/02-Texture-To-PNG]]、[[../README|技术首页]]。
