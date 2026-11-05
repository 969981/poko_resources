---
title: 原始文件与目录结构
tags: [pokopia, romfs, provenance]
updated: 2026-11-05
---
# 原始文件、目录与来源规则

## 数据分层

| 层级 | 实际位置 | 用途 |
| --- | --- | --- |
| 原始输入 | `2.0.1/exefs/main`、`2.0.1/romfs/` | 版本 2.0.1 的只读源数据 |
| 临时恢复 | `_work/2.0.1-restored/` | 7z 分卷恢复；**不提交** |
| 原始条目解包 | `UnPack/2.0.1/romfs/` | 保留原 RomFS 父目录、源文件名、条目内容 |
| 验证报告 | `UnPack/2.0.1/_reports/`、`_meta/2.0.1/` | 来源、范围、状态、哈希 |
| 应用资源 | `UnPack/2.0.1/Resources/` | Item/Pokemon/Textures/Localization 等可检索索引 |
| 研究脚本 | `Scripts/unpack/`、`Scripts/resources/` | 原生解包及转换 |
| .NET 解析 | `Pokopia.Binary/`、`Pokopia.Binary.Cli/`、`Pokopia.Binary.Checks/` | 独立辅助解析；不替换 Python 原生链 |

主要原始容器路径：

```text
2.0.1/
├── exefs/main
└── romfs/
    ├── LI_C0_R.IDX
    ├── LD_C0_R.BIN.7z.001  (后续分卷同一容器)
    └── motor_asset_re/KIDS_PLATFORM_OUNCE/
        ├── root.rdb / root.rdx
        ├── system.rdb / system.rdx
        ├── 0x<hash>.fdata(.7z.001...)
        ├── MountPoint_1/...
        ├── MountPoint_2/...
        └── data/0x<hash>.file...
```

实际发布路径把**恢复后的完整源文件名**作为目录，不把分卷名当成解包目录：

```text
UnPack/2.0.1/romfs/
├── LD_C0_R.BIN/
│   ├── decoded/00983.bin
│   ├── decoded/04645.bin ... 04653.bin
│   └── _manifest.csv
└── motor_asset_re/KIDS_PLATFORM_OUNCE/
    └── 0x00011c54.fdata/native/
        ├── root_038147_a0ce9914.g1t
        └── root_042753_b4b1fe49.texinfo
```

`decoded/` 是已成功解码的条目，`raw/` 是需要保留的原始片段，`_manifest.csv` 回溯源路径、SHA、序号、偏移、大小、状态。超大输出可为 `.part0001` 等按序拆分，必须核对清单后复原。排除 `romfs/movie_asset/`。不要拿仓库 Git 路径替代源 RomFS 的实际定位。

## 可复核样本指纹

- `2.0.1/exefs/main`：SHA-256 `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`。
- `UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin`：SHA-256 `2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`。

SHA 仅对指定版本/已审计的这两份文件成立；本地重跑须独立校验。参见 [[03-Unpacking-Workflow]]、[目录规范](../DIRECTORY.md)。