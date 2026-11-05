---
title: 原始ROM目录与资源对应路径
tags: [pokopia, resources, romfs, paths]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 原始文件 → 解包文件 → 按类别资源

## 原始文件（保留目录与文件名）

```text
2.0.1/
├── exefs/main
└── romfs/
    ├── LI_C0_R.IDX
    ├── LD_C0_R.BIN.7z.001 / .002 ...     # 分卷
    └── motor_asset_re/KIDS_PLATFORM_OUNCE/
        ├── root.rdb / root.rdx
        ├── system.rdb / system.rdx
        ├── 0x<hash>.fdata                 # 部分为分卷
        ├── MountPoint_1/0x<hash>.fdata
        └── MountPoint_2/0x<hash>.fdata
```

恢复后的逐条数据：`UnPack/2.0.1/romfs/`，原始路径和容器文件名不改。

| 内容 | 已验证的输入位置（仓库根目录相对） | 追踪索引/输出 |
| --- | --- | --- |
| 原生物品数据 | `UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin` | `Resources/Items/Native_2.0.1/native_item_raw_fields.csv` |
| 九语言物品文本 | 同一 `decoded/04645.bin`～`04653.bin` | `Resources/Items/Native_2.0.1/native_item_catalog.csv` |
| 主道具纹理 | `UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/root_042753_b4b1fe49.texinfo` | 1,333 条 UV |
| 主道具图像源 | 同目录 `root_038147_a0ce9914.g1t` | 双层 BC7、原生 `Icons/` |
| 宝可梦图例 | 同目录 `root_000147_00a2d79b.texinfo` + `root_017070_47b4eb66.g1t` | Pokémon Crosswalk |
| 其他 UI/场景 | 不限于一个包；各自的 `*.texinfo` / `*.g1t` | `Resources/Textures/Indexes/native_misc_texture_index.csv` |

以上 `Resources/` 均以 `UnPack/2.0.1/Resources/` 为前缀。**全量图片来源不能只用这里的示例父目录**，应从 CSV 的 `texinfo_path/g1t_path/record_index/layer` 精确定位。

## 实际资源目录

```text
UnPack/2.0.1/Resources/
├── Items/
│   ├── Native_2.0.1/Icons/          # 原生图
│   ├── Native_2.0.1/Extra272Candidates/
│   ├── Native_2.0.1/Extra14Candidates/
│   ├── Icons/                       # PokoHex 参考图，不能覆盖原生
│   └── Text/
├── Reactions/Icons/ + Text/        # PokoHex 参考
├── Villagers/Icons/ + Text/        # PokoHex 参考
├── Skills/Icons/ + Text/           # PokoHex 参考
├── Pokemon/NativeCandidates/{pokemon,pokemon_uni}/
├── Textures/Indexes/
├── Textures/MiscNativeBatches/batch_00...batch_16/
└── Localization/{Indexes,M7,M8,M9}/
```

关键查询：
[物品 1,615 个原生 ID 的总表](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/native_icon_complete_catalog.csv)、
[609 条宝可梦纹理 Hash 联接](../../../../UnPack/2.0.1/Resources/Pokemon/pokemon_identity_crosswalk.csv)、
[3,930 条其他图片的源路径](../../../../UnPack/2.0.1/Resources/Textures/Indexes/native_misc_png_catalog.csv)。
