# Pokopia 2.0.1 / M5 原生贴图管线技术文档

> 目标：从原始 RomFS 提取真正可溯源的 TEXINFO/G1T 纹理及 PNG，不把文件名编号、纹理 Hash、游戏道具 ID 和宝可梦图鉴编号混为一谈。2026-11-05。实际报告文件为事实来源；本文的数量是截至文档提交时的观察值。

## 0. 原始源、输出与执行环境

- 分支：`2.0.1_unpack`；原始只读输入目录：`UnPack/2.0.1/romfs/`。
- 主要包：`romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/`，还包括 `MountPoint_1/0x00176283.fdata` 与 `MountPoint_2/0x0017d6e2.fdata`。
- 索引证据：`Textures/Indexes/layout-textures.tsv`（KIDSOBJDB 哈希引用）、`Textures/texinfo_names.csv`、`Textures/Indexes/item_native_texture_links.csv`。
- Python 3.12、`Pillow>=11,<13` 支持 DDS BC7/BC3 转 PNG；`Scripts/resources/g1t_to_png.py` 是统一原生容器 / swizzle 实现。不要在研究格式时覆盖 `Resources/Items/Icons/` 下第三方 PokoHex PNG。
- 流程：源文件 SHA/大小 → TEXINFO 严格解析 → KIDSOBJDB 精确哈希边 → G1T 严格头/条目边界 → Ounce 排列 → 原生 UV 裁剪 → PNG SHA/长宽/透明度 → 参考图/游戏画面复核 → 身份 ID 映射。

## 1. 已验证文件结构

### 1.1 TEXINFO

头部小端 `u32 record_count`，记录长 **104 字节**；总长必须满足 `4 + count*104`。每条：

| 记录内偏移 | 长度 | 含义 |
| --- | ---: | --- |
| +0x00 | 64 | 以空字符截断的 ASCII/标识符纹理名 |
| +0x40 | 4 | 小端 u32 纹理条目/层号 |
| +0x44 | 32 | 8 个 float32，描述四顶点 UV；验证矩形与边界 |
| +0x64 | 4 | 原始 u32 尾字段，语义不明 |

在主道具 TEXINFO `root_042753_b4b1fe49.texinfo` 上，总长 138,636 字节、**1,333 条**；第 0/1 层分布 727/606。早期解析器仅识别单条记录，曾把 1,333 条地图错误标为 MISMATCH；现统一使用 `parse_texinfo()`，保持原始 `record_index`。

### 1.2 G1T

容器签名 `GT1G0600`，实际 `platform=0x18`。从容器读取 texture_count、偏移表、每条 format/dimensions/mips/payload；严格对照原始总长度，不按文件总长简单一分为二。已经遇到的原生 format：`0x66` BC7 和 `0x0A` BGRA8888；工具还支持部分 BC3/DXT5 候选格式。针对未知格式必须报错并留样本，不要静默转像素。

**平台差异（关键修复）**：旧版 Switch/Tegra `gobN` 与 Ounce/0x18 的 GOB 内部地址位序不同。2026-11-05 通过原版 G1T+TEXINFO 及 PokoHex 对照图逐块实验，确认 `x0/y1` 地址位应调换；新 `ounce1/2/4/8/16/32` 采用 Ounce 位序，`gobN` 保留为旧版比较。仅看到一张“似乎是宝可梦”的碎片不能视为验证成功。

### 1.3 道具图集

| 来源 | G1T 格式、尺寸 | 记录 | PNG 核验 |
| --- | --- | ---: | --- |
| 主道具双层，G1T `a0ce9914`，TEXINFO `b4b1fe49` | BC7、2048×2048×2、`ounce16` | 1,333 | 72×72；参考距离中位数 0.00528238，最大 0.01718695 |
| 第二道具图集，G1T `26a15463`，TEXINFO `51087a18` | BC7、2048×1024、`ounce16` | 272 | 72×72；中位数 0.00608996；1 个待复核 |
| 混合道具图集，G1T `35d04d04`，TEXINFO `c8d83a39` | 13 BC7 `ounce8` + 1 BGRA `ounce16` | 14 | 与参考距离最大 0.00888052 |

原生道具 1,619 条 PNG 来源，覆盖 **1,615 个不同道具 ID**；ID 1677、1764、1765、2742 出现两个版本，原生图与 PokoHex 参考图均不能未经核实互相覆盖。统一清单：`Items/Native_2.0.1/native_icon_complete_catalog.csv`；对照报告 `native_icon_coverage.json`、`native_icon_variant_review.csv`。

### 1.4 宝可梦图标

`Pokemon/pokemon_texture_index.csv`：609 条原始 TEXINFO 记录，按纹理名称去重 603；`icon_poke_` 301 条，`icon_poke_uni_` 308 条。580 个原始路径直接存在，29 个利用现有 decoded FDATA Git blob 别名恢复且保持二进制 SHA（`restore_29_g1t_report.json`）。609 张均已用 Ounce 布局导出，原生 Hash 关联 609/609；`Pokemon/NativeCandidates/pokemon_native_manifest.csv` 保存 PNG/G1T SHA、UV 与路径。普通图标示例：256×256 G1T UV 裁剪成 156×156 PNG，UNI 64×64 裁成 48×48。这是 **609 个纹理引用/资源版本**，绝非 609 个已验收物种。

`Pokemon/pokemon_identity_crosswalk.csv` 仍把 `native_species_id_verified` 留空；物种 ID 与原生纹理名的四位数字不得凭相似、排列顺序或外观自行“确认”。另见 `Pokemon/README.md`。

### 1.5 UI、场景与素材命名纹理

`Textures/Indexes/native_misc_texture_index.csv` 排除 `item_数字` 和 `icon_poke_` 后汇总 4,348 条纹理名称/UV；其中 3,930 条有唯一 KIDSOBJDB 索引边与原始 G1T 路径，368 条缺少可定位 G1T、50 条 KIDSOBJDB 索引有歧义。**名称包含 material 的 5 条并不意味着“全部材料只有 5 个”**，游戏材料可能位于 `item_XXXX` 道具中。随机分布的 25/25 条真实 G1T/TEXINFO 记录已经生成可读 PNG：`Textures/MiscNativeSamples/`。

后续导出使用统一元数据字段：`texture_name, texinfo_hash, g1t_hash, original_path, record_index, layer, uv, format, swizzle, width/height, png_sha256, decode_status, identity_status`。即使原图不透明、透明或空白也应保留，不得默默填补/删去。

## 2. 可复现命令

```bash
python -m pip install "Pillow>=11,<13>"
python -m unittest discover -s tests -p "test_g1t_to_png.py" -v
python -m Scripts.resources.export_native_item_atlas
python -m Scripts.resources.export_native_pokemon_icons
python -m Scripts.resources.audit_native_pokemon_identity
# 图源分类、素材与 UI 的分块导出见各脚本 --help / Actions 工作流。
```

GitHub Actions：`unpack-m5-export-native-icons.yml`、`unpack-m5-pokemon-export.yml`、`unpack-m5-pokemon-identity.yml`、`unpack-m5-reconcile-item-icons.yml`、`unpack-m5-ui-material-index.yml`、`unpack-m5-ui-material-preview.yml`。

## 3. 证据与验收分级

- **SOURCE_EXISTS**：原始 Git 文件/哈希可定位。不是图像身份。
- **INDEX_EDGE**：TEXINFO→KIDSOBJDB→G1T 关系唯一、原始字节/偏移符合；不是游戏物品/宝可梦 ID。
- **PNG_DECODED**：Ounce swizzle、原生 UV 裁剪后 PNG 可打开，大小/哈希/alpha 被验证；不等于像素逐点一致。
- **REFERENCE_SIMILAR**：与独立 PokoHex 参考图距离很小（启发式），不等于逐像素或游戏运行时验证。
- **NATIVE_ID_VERIFIED**：在原始游戏表、schema、资源使用方或真实运行时找到具偏移/调用证据的同 ID 绑定，且不存在重复来源歧义。当前宝可梦物种 ID 尚未达到。
- **GAME_VISIBLE_VERIFIED**：与实际游戏展示对照且记录版本、差异和样本；不得使用 PNG 解码成功代替。

任何失败应报告原始文件 SHA、完整索引键、错误类型和最小复现样本；优先保留未解决记录，不能在统计中消失。


## 4. M9 UI/场景/素材全批次导出终验（2026-11-05）

前文的“25 条抽样”是批量正式运行之前的阶段。最新代码与原版数据已经通过完整的 17 批验证：

| 核验结果 | 实际值 |
| --- | ---: |
| 非 item/pokemon TEXINFO 名称/UV 记录 | 4,348 |
| 具有唯一 KIDSOBJDB→G1T 边且原始文件可定位 | **3,930** |
| 实际导出 PNG 候选 | **3,930** |
| 已导出但全透明的 4×4 占位图 | **5** |
| 已导出且含非零 Alpha 的图 | **3,925** |
| 解码/UV/Hash 失败 | **0** |
| 没有对应记录的批次或漏行 | **0** |
| 暂未唯一关联的剩余记录 | **418**（G1T 368、索引 50） |

统一总账 `Resources/Textures/Indexes/native_misc_png_catalog.csv`，总报告 `native_misc_png_summary.json`，全透明样本说明 `native_misc_transparent_review.md`。每一批存放在 `Textures/MiscNativeBatches/batch_00`～`batch_16`，目录包含原始源键、PNG、SHA/UV 审计和预览拼图。全部 17 批完成后，合并脚本严格检查 3,930 条记录**来源键无重叠、无缺失、原始索引 SHA 一致**，不依赖仅看 GitHub Actions 运行状态。验证工作流：[M9 17 批导出](https://github.com/969981/poko_resources/actions/runs/41947563611)；[全批次合并核验](https://github.com/969981/poko_resources/actions/runs/41949088320)。

5 张 4×4 全透明的源名称包括 `0000_prt_square_transparent`、`0300_base_character_table` 和 3 张 `icon_skill`；保留为 `TRANSPARENT_CANDIDATE_REVIEW` 而不删除。其余 418 条缺失/歧义仍保留索引，没有被强行合并为 3,930 张图像。**这里的素材仅代表源纹理名候选，游戏材料类型的原生证明仍需反查 00983.bin 与其消费者。**

