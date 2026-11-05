---
title: 转换后数据读取与校验
tags: [pokopia, csv, sqlite, json, validation]
updated: 2026-11-05
---
# 如何读取和使用转换后的数据

## 物品名称和图标

- 文本：`UnPack/2.0.1/Resources/Items/Text/text_item_zhs.txt`（其他语言换后缀），**行号从 0 计起即 item_id**，保留空行；读取时使用 UTF-8，不进行字典排序。
- 九语言与证据：`Resources/Items/item_catalog.csv`、`Resources/Items/Native_2.0.1/validation.json`。
- 原生 PNG：`Resources/Items/Native_2.0.1/native_icon_complete_catalog.csv`，使用 `item_id` 与语言文本连接；如果同 ID 多来源，保留源 `g1t_hash`/`texinfo_hash`，不得无提示选一张覆盖。
- 第三方图片：`Resources/Items/Icons/` 来自 PokoHex 参考资源，应标注第三方来源和固定提交，不与本游戏原版提取物混写。这里 `Resources/` 是 `UnPack/2.0.1/Resources/` 的缩写。

## 宝可梦纹理和 UI 图

- 宝可梦：`Resources/Pokemon/pokemon_texture_index.csv`、`Resources/Pokemon/NativeCandidates/pokemon_native_manifest.csv`、`Resources/Pokemon/pokemon_identity_crosswalk.csv`。
- UI/素材：`Resources/Textures/Indexes/native_misc_texture_index.csv`、`native_misc_png_catalog.csv`，输出 `Resources/Textures/MiscNativeBatches/`。
- 文件名的数字可能是纹理名称成分，**不能直接当作**宝可梦 `species_id`；本版已确认的 609 个纹理引用不等于 609 个不同物种。

## M3 SQLite / 资源图谱

工具入口 `Scripts/unpack/m3_database.py`，研究文档 [M3_SQLITE.md](../M3_SQLITE.md)。原始资源索引、KIDSOBJDB 字段和数值候选在数据库中分层存储；数据库为大型构建产物（可能保存在 Actions artifact），不是 `UnPack/` Git 已上传的必有文件。

示例：先依据数据库的具体 schema 检查字段，再运行查询，**不可假设表名**：

```bash
sqlite3 YOUR_M3_DB.sqlite ".tables"
sqlite3 YOUR_M3_DB.sqlite ".schema"
sqlite3 YOUR_M3_DB.sqlite "PRAGMA integrity_check;"
```

## 程序调用的最小证据字段

建议应用层 CSV/JSON 对外统一携带：

`game_version, source_path, source_sha256, entry_index, byte_offset, raw_record_id, resource_hash, texinfo_hash, g1t_hash, png_sha256, language, text_id, evidence_grade, verification_status`。

出现 `UNKNOWN`、`UNVERIFIED_CANDIDATE`、`PNG_CANDIDATE_UNVERIFIED` 时在 UI 标记候选，不静默改写为正式类型。

## 快速文件核验

```bash
python -c "import hashlib,pathlib; p=pathlib.Path('UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin'); print(p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest())"
```

核对输出应与 [[01-Source-Layout]] 的指定 SHA 相符；否则停止套用已研究偏移，先检查版本、分卷恢复和原始清单。