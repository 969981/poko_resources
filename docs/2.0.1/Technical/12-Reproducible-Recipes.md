---
title: 从原始资源到图像文本的可复现配方
aliases: [Pokopia 解包操作手册, 实际运行命令]
tags: [pokopia, workflow, 7zip, python, export]
game_version: "2.0.1"
status: COMMANDS_SOURCE_CHECKED
updated: 2026-11-05
---
# 从输入到输出的实际操作配方（Windows PowerShell）

> 下列参数已对照现有 CLI 源码。命令只是**执行步骤**，不是本轮对用户本地文件执行成功的报告。所有命令在仓库根目录运行；不要直接覆盖游戏输入、第三方图标或原始二进制。

## A. 检查分卷与物理输入

```powershell
python -m Scripts.unpack.inventory --source 2.0.1 --output _meta/2.0.1
7z t "2.0.1/romfs/LD_C0_R.BIN.7z.001"
7z x "2.0.1/romfs/LD_C0_R.BIN.7z.001" -o_work/2.0.1-restored/romfs
python -m Scripts.unpack.inventory --source 2.0.1 --output _meta/2.0.1 --hash --test-7z
```

前提：该 BIN 的所有 `.7z.00N` 分卷齐全，磁盘有足够空间。不要把 `.001` 当成完整 BIN 直接解析。

## B. LINKDATA 索引、少量解码、只读验收

```powershell
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --output _meta/2.0.1/linkdata
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --bin _work/2.0.1-restored/romfs/LD_C0_R.BIN --output _work/linkdata-nine-text --start 4645 --limit 9 --decode --resume
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --bin _work/2.0.1-restored/romfs/LD_C0_R.BIN --output _meta/2.0.1/linkdata-verify --decode --verify-only --limit 250
```

`--start 4645 --limit 9` 是物品九语言表条目范围的**定向样本**。它先输出到临时目录；用于下游文本脚本的仓库标准输入目录是已发布、带来源清单的 `UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/`，两者不能无验证地视为同一个输出。完整发布流程参阅 [[03-Unpacking-Workflow]] 和 [Scripts 说明](../../../Scripts/README.md)。

## C. RDB/RDX/FDATA 原始资源

```powershell
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _meta/2.0.1/ktrdb
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _work/ktrdb-sample --extract --decode --limit 20 --resume
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _meta/2.0.1/ktrdb-verify --extract --decode --verify-only --limit 250
```

前提：已经恢复所需 FDATA。索引成功但物理文件缺失时保留 `CONTAINER_NOT_PRESENT`；`--verify-only` **不会输出游戏素材**。

## D. TEXINFO/G1T → 候选 PNG

```powershell
python -m pip install "Pillow>=11,<13"
python -m unittest discover -s tests -p "test_g1t_to_png.py" -v
python -m Scripts.resources.g1t_to_png --input UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native --layouts ounce2,ounce8,ounce16 --max-files 5 --dest _work/g1t-candidates
```

通用工具可能生成多个布局的候选图，不会自行确认哪个符合游戏画面。若需要已审计的**道具主图集**，使用专用导出器：

```powershell
python -m Scripts.resources.export_native_item_atlas
python -m Scripts.resources.reconcile_native_item_icons
```

默认读取 `root_038147_a0ce9914.g1t`、`root_042753_b4b1fe49.texinfo` 以及 `Textures/Indexes/item_atlas_1333_uv.csv`；结果在 `Resources/Items/Native_2.0.1/`。不得用导出 PNG 覆盖 PokoHex 的 `Resources/Items/Icons/`。

宝可梦和其他 UI/素材分开处理：

```powershell
python -m Scripts.resources.export_native_pokemon_icons
python -m Scripts.resources.export_native_misc_batches --batch 0 --batch-size 240
python -m Scripts.resources.reconcile_native_misc_batches
```

`export_native_pokemon_icons` 检查 609 条原始索引输入；原生纹理来源成立仍不等于 609 个经过证明的物种 ID。UI/素材按索引批量导出，未跑全批次时不要加入 `--require-complete` 宣称完整。

## E. 原生九语言文本 → CSV/JSON

```powershell
python -m Scripts.resources.discover_native_text --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.export_native_localization --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.recover_native_text_ids --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
python -m Scripts.resources.link_native_text_references --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded
```

输入必须包含真实 `00983.bin`、`04645.bin`～`04653.bin` 以及这些脚本依赖的既有审计/索引。九语言**物品名**已核验；M7/M8 的剧情、UI、任务外键候选仍不能作正式归类。输出位置见 [[05-Localization]]。

## F. 只读 .NET 交叉解析

```powershell
git submodule update --init --recursive ThirdParty/Edoke
dotnet build Pokopia.Binary.Cli/Pokopia.Binary.Cli.csproj -c Release
dotnet run --project Pokopia.Binary.Checks -c Release
dotnet run --project Pokopia.Binary.Cli -c Release -- texinfo UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/root_042753_b4b1fe49.texinfo
```

输出为只读 JSON lines；.NET 项目不负责 PNG、Oodle 或写回。命令全集：[Pokopia.Binary README](../../../Pokopia.Binary/README.md)。

## 完成一次流程的最低验收

- 原始文件 SHA/尺寸与来源版本一致；分卷 test 通过。
- 索引偏移不越界，raw 与 decoded 都有来源记录；成功/失败数量可对账。
- PNG 有 G1T、TEXINFO、UV、layout、尺寸、SHA；图片身份另算。
- 多语言保留空行/空槽/控制符，语言和行号不发生重排。
- 输出 manifest、CSV/JSON 与原始文件路径可逆向追踪；证据等级按 [[08-Evidence-And-Open-Questions]]。
