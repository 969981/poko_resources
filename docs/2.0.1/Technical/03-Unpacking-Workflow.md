---
title: 原始资源解包操作
tags: [pokopia, unpack, sevenzip, workflow]
updated: 2026-11-05
---
# 从分卷到已核验条目

全部命令在**仓库根目录**运行。第一阶段只读审计，确认 7z 分卷、空间和 SHA，再做实体导出。

## M0：检查原始文件

```powershell
python -m Scripts.unpack.inventory --source 2.0.1 --output _meta/2.0.1
python -m Scripts.unpack.inventory --source 2.0.1 --output _meta/2.0.1 --hash --test-7z
```

## 恢复分卷（7-Zip）

```powershell
7z t "2.0.1/romfs/LD_C0_R.BIN.7z.001"
7z x "2.0.1/romfs/LD_C0_R.BIN.7z.001" -o_work/2.0.1-restored/romfs
```

`.001/.002` 是同一源文件的分卷。必须备齐文件、通过 `7z t`，不要将压缩分卷当作可解析的 BIN/FDATA。大型 FDATA 同理，在对应源目录恢复至临时工作目录。

## M1：LINKDATA 索引/实体

```powershell
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --output _meta/2.0.1/linkdata
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --bin _work/2.0.1-restored/romfs/LD_C0_R.BIN --output UnPack/2.0.1/LINKDATA --start 0 --limit 20 --decode --resume
```

保留 `raw` 和解码状态；遇到未支持 codec/损坏记录，不能仅凭读取成功写成 `DECOMPRESSED`。

## M2：KT RDB/RDX + FDATA

```powershell
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _meta/2.0.1/ktrdb
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output UnPack/2.0.1/KTRDB --extract --decode --limit 20 --resume
```

先看 `CONTAINER_NOT_PRESENT`，确认是否遗漏 FDATA；不能把缺文件计为解码失败。

## 只验证，不导出游戏资源

```powershell
python -m Scripts.unpack.smoke --source 2.0.1 --output _meta/2.0.1/smoke
python -m Scripts.unpack.full_pipeline --source 2.0.1 --work _work/2.0.1-verify --output _meta/2.0.1/full --sevenzip 7z --verify-only
python -m unittest discover -s tests -v
```

`full_pipeline` 强制 `--verify-only`。真实 GitHub 路径镜像由 `Scripts/unpack/publish.py` 和大容器专用 `publish_stream.py` 以及对应 Actions 工作流发布；查看其 `--help`、工作流参数与源目录，勿误将验证命令当作发布。

## 结果验收

状态分开记录：`INDEXED`、`LOCATED`、`EXTRACTED`、`DECOMPRESSED`、`DECODE_FAILED`、`CONTAINER_NOT_PRESENT`、`PUBLISHED`、`SKIPPED_BATCH_BUDGET`。发布完成须在分支实际查到 `decoded/` 文件和 `_manifest.csv`，并与 SHA 对账，不能只看 Actions 绿灯。

相关：[[01-Source-Layout]]、[原有 Scripts 使用说明](../../../Scripts/README.md)、[解包目录约束](../DIRECTORY.md)、[真实产物 README](../../../UnPack/2.0.1/README.md)。