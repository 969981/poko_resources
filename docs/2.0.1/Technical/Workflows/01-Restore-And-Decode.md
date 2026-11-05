---
title: 从分卷到原始资源还原操作卡
tags: [pokopia, 2-0-1, unpack, 7zip, workflow]
game_version: "2.0.1"
status: ACTIVE
updated: 2026-11-05
---
# 分卷恢复 → LINKDATA / RDB / FDATA 解码

## 阶段 A：检查输入而不是直接写回仓库

```powershell
python -m Scripts.unpack.inventory --source 2.0.1 --output _meta/2.0.1
7z t "2.0.1/romfs/LD_C0_R.BIN.7z.001"
7z x "2.0.1/romfs/LD_C0_R.BIN.7z.001" -o_work/2.0.1-restored/romfs
```

所有分卷必须齐全；若输入是其他 RDB/FDATA 分卷，同样先恢复。**不要**将 `.7z.001` 直接交给格式解析器，也不要在 `2.0.1/` 原始输入上修改二进制。

## 阶段 B：LINKDATA

```powershell
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --output _meta/2.0.1/linkdata
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --bin _work/2.0.1-restored/romfs/LD_C0_R.BIN --output _work/decoded-sample --start 4645 --limit 9 --decode --resume
```

检查 `raw/04645.bin` 与 `decoded/04645.bin`，从报告确认状态与各自 SHA。`--start 4645 --limit 9` 不是解包全部内容。

## 阶段 C：RDB/RDX → FDATA

```powershell
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _meta/2.0.1/ktrdb
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _work/ktrdb-sample --extract --decode --limit 20 --resume
```

缺失 FDATA 时先补齐物理文件，不修改解析器来“伪造成功”。`--verify-only` 用于字节/SHA 校验，不导出素材。

## 阶段 D：报告的状态必须可追溯

在验收表中区分 `INDEXED`、`EXTRACTED`、`DECOMPRESSED`、`DECODE_FAILED`、`CONTAINER_NOT_PRESENT`、`UNSUPPORTED_FOOTER_LAYOUT`。对任意成功条目记录原始索引位置、压缩原字节 SHA、解码 SHA、最终输出相对路径；失败不允许静默跳过。

延伸格式：[[../Formats/01-LINKDATA-IDX-BIN]]、[[../Formats/02-RDB-RDX-FDATA-IDRK]]。
