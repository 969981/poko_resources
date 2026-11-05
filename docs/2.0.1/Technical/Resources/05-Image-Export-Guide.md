---
title: 参考图导入与原生G1T到PNG导出流程
tags: [pokopia, resources, images, export, powershell]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 图片提取和转换：按来源选择脚本

所有命令从 `poko_resources` 仓库根目录执行。先确保已有合法的原始解包源文件。**参考图是复制导入，原生图才是 G1T 解码＋UV 裁剪**；覆盖原生 PNG 前建议使用独立工作副本。

## 0. 环境和测试

```powershell
python --version
python -m pip install "Pillow>=11,<13"
python -m unittest discover -s tests -p "test_g1t_to_png.py" -v
git status --short
New-Item -ItemType Directory -Force "_work" | Out-Null
```

PNG 导出时保留 `texinfo_path`、`g1t_path`、`record_index`、`layer`、UV、layout、`png_sha256`，不要仅以视觉相似性命名为官方物品/物种 ID。

## A. 表情、村民、技能：PokoHex 参考图导入

```powershell
git clone https://github.com/969981/PokoHex.git _work/PokoHex
git -C _work/PokoHex checkout c71d2b73fb9d8cfe99c1067e6bfadfd19f60bf78
python -m Scripts.resources.import_pokohex_extra --source _work/PokoHex --dest _work/reference-resources
```

上游 PNG 分别是 `PokoHex/Resources/Reaction`、`Villager`、`Skill`；导入九语言 `PokoHex.Core/Resources/text/<lang>/text_...txt`，解析村民的 `villager_portrait.bin`。输出 `Reactions/`、`Villagers/`、`Skills/` 的 CSV、PNG、SHA。源码：[import_pokohex_extra.py](../../../../Scripts/resources/import_pokohex_extra.py)。

物品 PokoHex 参考导入使用 `python -m Scripts.resources.import_pokohex --help`，需要另外准备 M3 类型索引，参考 [Resources README](../../../../UnPack/2.0.1/Resources/README.md)。不能把这条当作原生 2.0.1 G1T 解包。

## B. 物品原生 PNG：1,333 + 272 + 14

```powershell
python -m Scripts.resources.export_native_item_atlas --help
python -m Scripts.resources.export_native_item_atlas
python -m Scripts.resources.export_native_atlas272
python -m Scripts.resources.export_special14
python -m Scripts.resources.reconcile_native_item_icons
```

主图集已针对 2.0.1 原始 TEXINFO + 双层 2048×2048 BC7 校准：`platform 0x18 → ounce16 unswizzle → BC7 → RGBA → UV crop → 72×72 PNG`。特殊图集含 Ounce8 BC7 与 Ounce16 BGRA。4 个重复物品 ID 的不同原生版本不覆盖。

**注意**：部分命令默认会重建 `Resources/Items/Native_2.0.1/` 下的派生图像与报告；运行前检查 `--help`、备份旧 manifest，或在独立克隆执行。源文件 SHA 和图像 SHA 应与 [native_icon_complete_catalog.csv](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/native_icon_complete_catalog.csv) 对账。

## C. 原生宝可梦纹理

```powershell
python -m Scripts.resources.export_native_pokemon_icons
python -m Scripts.resources.audit_native_pokemon_identity
```

索引 `Pokemon/pokemon_texture_index.csv` → 原始 TEXINFO/G1T → Ounce2/8 → UV crop → `Pokemon/NativeCandidates/{pokemon,pokemon_uni}/`。609 个源限定候选 PNG 已有记录；名称数字 ≠ 已证物种 ID，仍保留 `PNG_CANDIDATE_UNVERIFIED`。

## D. UI、场景、装饰、提示、素材名等：17 批

```powershell
python -m Scripts.resources.export_native_misc_batches --batch 0 --batch-size 240 --plan _work/batch00.json
# 源文件已完整存在后才运行真实解码：
python -m Scripts.resources.export_native_misc_batches --batch 0 --batch-size 240 --read-plan _work/batch00.json
# 只有 17 批全部存在时才能通过完整验收：
python -m Scripts.resources.reconcile_native_misc_batches --require-complete
```

`--plan` 列出该批精确源文件及索引快照，`--read-plan` 才实际读取并生成默认 `Textures/MiscNativeBatches/batch_00/`。并非自动下载缺失的原始文件；计划文件验证会拒绝索引变动。每批 `batch_audit.json`、`misc_native_sample_manifest.csv` 可反查状态与失败原因。

小规模样本可用：

```powershell
python -m Scripts.resources.export_native_misc_samples --plan _work/misc-samples.json
python -m Scripts.resources.export_native_misc_samples --read-plan _work/misc-samples.json --out _work/misc-preview
```

## E. 单张 G1T 的通用试解

```powershell
python -m Scripts.resources.g1t_to_png --help
python -m Scripts.resources.g1t_to_png --input UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native --layouts ounce2,ounce8,ounce16 --max-files 5 --dest _work/texture-preview
```

通用工具可能输出布局候选，**不是自动识别正确源 ID**。常见问题：BC7/BC3/BGRA 格式不匹配，旧 Tegra GOB 与 Ounce 混淆、swizzle、mip、Alpha、垂直原点、UV 和 layer 混用。

验收证据：
[物品图总表](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/native_icon_complete_catalog.csv) · [宝可梦 manifest](../../../../UnPack/2.0.1/Resources/Pokemon/NativeCandidates/pokemon_native_manifest.csv) · [其他 PNG 全量表](../../../../UnPack/2.0.1/Resources/Textures/Indexes/native_misc_png_catalog.csv) · [Validation](../Validation/README.md)。
