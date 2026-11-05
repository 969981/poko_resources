---
title: 脚本和工具使用速查
tags: [pokopia, tools, python, commands]
updated: 2026-11-05
---
# 脚本、工具与命令速查

**所有命令都在仓库根目录执行**。基本环境 Python 3.10+；M0–M2 主体使用标准库；PNG 需要 `Pillow>=11,<13`，部分 ARM64 研究脚本还需要 `lz4>=4,<5`、`capstone>=5,<6`。`7z` 需单独安装并进入 PATH。对于脚本的可选参数，优先运行 `python -m 模块 --help`，不要套用不同版本脚本的参数。

## 容器和原生结构

| 功能 | 模块/入口 |
| --- | --- |
| M0 输入/分卷盘点 | `python -m Scripts.unpack.inventory` |
| LINKDATA IDX/BIN | `python -m Scripts.unpack.linkdata` |
| RDB/RDX/FDATA | `python -m Scripts.unpack.ktrdb` |
| 全流程只读验证 | `python -m Scripts.unpack.full_pipeline` |
| 发布到原始路径镜像 | `Scripts/unpack/publish.py`、`publish_stream.py` |
| 资源类型与 SQLite | `Scripts/unpack/m3_database.py`、`m3_types.py` |
| KIDSOBJDB 对象数据 | `Scripts/unpack/decode_kidsobjdb.py`、`m4_batch.py` |
| .NET 只读二进制解析 | `Pokopia.Binary/`、`Pokopia.Binary.Cli/`，具体命令见项目源码/README |

## 原生图像和索引

| 功能 | 脚本 | 输出/注意 |
| --- | --- | --- |
| G1T/TEXINFO 基础解码 | `g1t_to_png.py` | 自定义路径、swizzle 候选，PNG 校验 |
| 原版道具主图集 | `export_native_item_atlas.py` | 1,333 个 UV 裁图及 manifest |
| 宝可梦图标 | `export_native_pokemon_icons.py` | 源哈希 + 候选 PNG，物种 ID 不填 |
| 原生图标对账 | `reconcile_native_item_icons.py` | 不覆盖第三方图 |
| UI/素材纹理索引 | `build_native_misc_texture_index.py` | 原始关联、歧义标志 |
| UI/素材按批导出 | `export_native_misc_batches.py` | `--batch`、`--batch-size` |
| UI/素材批次归并 | `reconcile_native_misc_batches.py` | 全量行数、SHA、重复/缺失检查 |

除首列注明的入口外，本表脚本均位于 `Scripts/resources/`，可使用 `python -m Scripts.resources.<不带.py的脚本名>`。

## 文本与身份

| 功能 | 模块 |
| --- | --- |
| 简单原生文本定位 | `Scripts.resources.discover_native_text` |
| 九语言原生物品验证及候选 | `Scripts.resources.export_native_localization` |
| M7 定长结构、文本 ID | `Scripts.resources.recover_native_text_ids` |
| 原生外键候选 | `Scripts.resources.link_native_text_references` |
| M9 KIDSOBJDB/RNK 追踪 | `Scripts.resources.m9_kidsobjdb_properties`、`m9_rnk_name_tables` |
| 物品原始字段 | `Scripts.resources.analyze_native_item_fields` |
| 物种纹理身份审计 | `Scripts.resources.audit_native_pokemon_identity` |
| 读取物品虚函数/字段证据 | `Scripts.resources.m18_original_consumer_callgraph` |
| 983 NID 反证 | `Scripts.resources.m20_item983_cache_provenance` |

## 可复制的最短验证

```bash
python -m unittest discover -s tests -v
python -m Scripts.unpack.smoke --source 2.0.1 --output _meta/2.0.1/smoke
python -m Scripts.resources.export_native_item_atlas
python -m Scripts.resources.recover_native_text_ids --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.m20_item983_cache_provenance
```

注意：第三方工具 `RDBExplorer`、`fdata_dump`、`Cethleann`、`Edoke` 可作为交叉参考，但版本、实际格式兼容性和独立成功样本**必须逐项验证**。现有 .NET 10 项目仅作辅助，不应整体迁移或删除 Python 证据链。

完整参数和报告路径以仓库中的 [Scripts/README](../../../Scripts/README.md)、[M5 原生纹理文档](../M5_NATIVE_TEXTURE_PIPELINE.md) 和各脚本自身为准。