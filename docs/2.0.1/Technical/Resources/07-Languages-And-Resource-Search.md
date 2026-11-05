---
title: 资源语言表原始文件位置及按ID检索
tags: [pokopia, resources, localization, search, powershell]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 九语言文本来源与资源路径查询

## 已原生对账的物品名称

同一目录 `UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/`：

| 语言 | 文件 | 语言 | 文件 | 语言 | 文件 |
| --- | --- | --- | --- | --- | --- |
| jp | 04645.bin | en | 04646.bin | fr | 04647.bin |
| it | 04648.bin | de | 04649.bin | es | 04650.bin |
| zht | 04651.bin | ko | 04652.bin | zhs | 04653.bin |

原生 item 表 `00983.bin` 的 `+0x22` u16 连接**物品名称索引**。已经验证九语每个 4600 物品槽；例如日语源文件 `04645.bin` 本身是 3001 条 × 32-byte 的 v2 文本索引，不能把物品槽数误当单表内部条目数。

## 参考文本：表情 / 村民 / 技能

在 `UnPack/2.0.1/Resources/{Reactions,Villagers,Skills}/Text/` 中，每种 `text_<kind>_<lang>.txt` 来自 PokoHex 固定版本 `PokoHex.Core/Resources/text/<lang>/`。这些表的行号可以用于 PokoHex catalog 的反查，但**尚未证明它们分别对应游戏原生 LINKDATA 的哪个 entry 和 text_id**。

[M7 报告](../../../../UnPack/2.0.1/Resources/Localization/M7/m7_report.json) 已解析 2,738 个原生文本表、195 组九语言；剧情/任务/建筑/村民外键仍未恢复。字符串原始 `<$...>` 标签、私有字形与空行需保留。

```powershell
python -m Scripts.resources.recover_native_text_ids --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded --dest _work/m7-check
python -m Scripts.resources.export_native_localization --help
```

## PowerShell 按 ID 查源路径

```powershell
$R = "UnPack/2.0.1/Resources"
# 物品 101：名称、原生 PNG、分类原始数值
Import-Csv "$R/Items/Native_2.0.1/native_icon_complete_catalog.csv" |
  Where-Object { [int]$_.item_id -eq 101 } |
  Select-Object item_id,zhs,en,native_png,source_g1t_hash,source_texinfo_hash
Import-Csv "$R/Items/Native_2.0.1/native_item_raw_fields.csv" |
  Where-Object { [int]$_.item_id -eq 101 } |
  Select-Object item_id,name_zhs,category_candidate_u8_at_0x26,group_raw_u8_at_0x39,group_raw_u8_at_0x3a

# 表情 ID 6：直接使用 CSV 的 icon_path
Import-Csv "$R/Reactions/reaction_catalog.csv" |
  Where-Object { [int]$_.reaction_id -eq 6 } |
  Select-Object reaction_id,en,zhs,icon_path

# 村民 ID 49：注意是 portrait_id，不是 villager_id 拼文件名
Import-Csv "$R/Villagers/villager_catalog.csv" |
  Where-Object { [int]$_.villager_id -eq 49 } |
  Select-Object villager_id,en,zhs,portrait_id_raw_u16,icon_path

# 技能 ID 1：有轮盘/公开标记
Import-Csv "$R/Skills/skill_catalog.csv" |
  Where-Object { [int]$_.skill_id -eq 1 } |
  Select-Object skill_id,en,zhs,is_public,can_use_wheel,icon_path
```

上述三类参考 `icon_path` 相对 `$R`；物品 `native_png` 通常已经是相对**仓库根目录**的完整路径，不能再重复拼接 `$R`。

## 按图片名称查完整原生路径

```powershell
$index = "$R/Textures/Indexes/native_misc_texture_index.csv"
Import-Csv $index |
  Where-Object { $_.texture_name -match 'reaction|emote|villager|shop|still|furniture|material' } |
  Select-Object -First 40 texture_name,category_candidate,texinfo_path,record_index,layer,g1t_path,status

Import-Csv "$R/Pokemon/pokemon_identity_crosswalk.csv" |
  Where-Object { $_.texture_name -like "*icon_poke_uni_0180*" } |
  Select-Object texture_name,texinfo_filename,g1t_filename,objdb_file,swizzle_layout,png_path,native_species_id_verified
```

结果为空只说明**目前索引没有找到这个名称**，不代表游戏没有资源；名字相似也不足以证明 ID。新的发现请带 `source_sha256 / source_path / record_index / byte_offset / decoder / png_sha256 / status` 更新相应 Obsidian 专题。

[返回资源首页](README.md) · [原生数据验收](../Validation/README.md)。
