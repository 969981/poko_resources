---
title: 工具链与依赖矩阵
aliases: [Pokopia 工具链, 解包工具安装]
tags: [pokopia, tooling, python, dotnet, obsidian]
game_version: "2.0.1"
status: VERIFIED_ENTRYPOINTS
updated: 2026-11-05
---
# 工具链、依赖和适用边界

> 本页只描述仓库已有入口；没有运行的命令不等于已在本机成功通过。命令均在 `poko_resources` 仓库根目录执行；输入文件只读，输出写到 `_work/`、`_meta/` 或 `UnPack/`。

## 安装条件

| 工具 | 要求/用途 | 本项目使用方式 |
| --- | --- | --- |
| Git + Git LFS（若实际需要） | 获取仓库及其对象；不代替游戏文件验证 | `git clone -b 2.0.1_unpack --recurse-submodules ...` |
| Python | 3.10+；M0–M2 主流程主要是标准库 | `python -m Scripts.unpack.<module>` |
| 7-Zip | 可在 PATH 调用 `7z`；恢复 `.7z.001` | `7z t`、`7z x`，先校验分卷齐全 |
| Pillow | 图像导出：`Pillow>=11,<13` | `python -m pip install "Pillow>=11,<13"` |
| lz4、capstone | 仅部分 ARM64/研究脚本按需使用 | 先查具体脚本 imports / CI，不能当全仓库必需 |
| .NET SDK 10 | `Pokopia.Binary*` 只读辅助解析 | `dotnet build`、`dotnet run` |
| Edoke | `ThirdParty/Edoke` 固定 Git submodule 版本 | `git submodule update --init --recursive ThirdParty/Edoke` |
| SQLite CLI（可选） | 检查导出的数据库模式和完整性 | `sqlite3 database.sqlite ".schema"` |

```powershell
git clone --recurse-submodules -b 2.0.1_unpack https://github.com/969981/poko_resources.git
cd poko_resources
python --version
7z i
python -m pip install "Pillow>=11,<13"
python -m unittest discover -s tests -v
dotnet build Pokopia.Binary.Cli/Pokopia.Binary.Cli.csproj -c Release
dotnet run --project Pokopia.Binary.Checks -c Release
```

## 用哪个工具处理哪种原始文件

| 输入格式 | 对应脚本 / 命令入口 | 典型输出 | 不具备的能力 |
| --- | --- | --- | --- |
| `*.7z.001` | 7-Zip | 解压后的真实 BIN/FDATA | 不会自动解释内部游戏记录 |
| `LI_C0_R.IDX` + `LD_C0_R.BIN` | `Scripts.unpack.linkdata` | 索引、raw/decoded、SHA 报告 | 标准 zlib 失败不等于其他 codec 已支持 |
| `*.rdb` + `*.rdx` + `*.fdata` | `Scripts.unpack.ktrdb` | 文件定位/提取/解码状态 | 不能凭 Hash 判断游戏内身份 |
| `*.kidsobjdb` | `Scripts.unpack.decode_kidsobjdb` | IDOK/RDOK/字段记录 | 未知字段仍为 UNKNOWN |
| 大型索引/对象字段 | `Pokopia.Binary.Cli` | 只读 NDJSON | 不做 Oodle、PNG、文本翻译、写回 |
| `*.texinfo` + `*.g1t` | `Scripts.resources.g1t_to_png` | 候选 PNG、解码诊断 | 不自动证明图像或游戏 ID |
| 已关联道具原生图集 | `Scripts.resources.export_native_item_atlas` | PNG + 原生清单 | 不覆盖第三方 `Items/Icons` |
| 宝可梦纹理源 | `Scripts.resources.export_native_pokemon_icons` | 纹理候选和来源 Hash | 不能把纹理号当物种 ID |
| 原生多语言 BIN | `Scripts.resources.export_native_localization` / `recover_native_text_ids` | CSV/JSON/M7 报告 | 非物品剧情/建筑外键尚未闭合 |
| 解析索引/物理审计 | `Scripts.unpack.m3_database` / `Pokopia.Binary.Cli audit-fdata` | SQLite、逐条证据 | 数值相等不等于引用关系 |

## 快速自检

```powershell
python -m Scripts.unpack.linkdata --help
python -m Scripts.unpack.ktrdb --help
python -m Scripts.resources.g1t_to_png --help
python -m Scripts.resources.recover_native_text_ids --help
dotnet run --project Pokopia.Binary.Cli -c Release -- texinfo UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/root_042753_b4b1fe49.texinfo
```

最后一条需要该原生文件确实已恢复到所示位置。参阅 [Python 脚本说明](../../../Scripts/README.md)、[.NET 已实现命令](../../../Pokopia.Binary/README.md)、[[12-Reproducible-Recipes]]、[[14-Troubleshooting-And-Validation]]。
