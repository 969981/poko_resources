# Pokopia 2.0.1 — 原生宝可梦纹理 / Original Pokémon icon assets

这里存放 **Pokopia 2.0.1 RomFS 原始 TEXINFO + G1T** 导出的宝可梦图标候选，跟 PokoHex 道具资源、游戏图鉴 ID、村民 ID 分开处理。

## 最新可复核结果（2026-11-05）

| 项目 | 核对结果 |
| --- | ---: |
| 原生 TEXINFO 宝可梦图标记录 | 609 |
| 按 texture_name 去重 | 603（另外 6 条是不同 Hash 的原生版本） |
| 普通 `icon_poke_` | 301 |
| `icon_poke_uni_` | 308 |
| 原始 G1T 文件物理定位成功 | 609 / 609 |
| 原生 FDATA 解码字节恢复的 G1T 别名 | 29 |
| source-qualified PNG 候选 | 609 张 |
| TEXINFO/G1T 与 KIDSOBJDB 哈希索引关系 | 609 / 609 |
| **可证明的物种 ID 对照** | **0**（尚未恢复原生引用表） |

所有候选使用 platform **0x18** 的 Ounce/GOB 字节排列，而不是旧版 Switch/Tegra 通用 `gobN`。其根因是 GOB 内部分地址位序不同。对比原始物品 G1T 与 PokoHex 图标后，已从失真的 `gob8/gob2` 修复为 `ounce8/ounce2`；64px 图集经 UV 取 48px、256px 图集经 UV 取 156px 等，都根据 *原始 TEXINFO* 确定，不盲裁。

- `pokemon_texture_index.csv`：609 条 TEXINFO→G1T 源路径、Hash、UV 和别名来源。
- `NativeCandidates/pokemon_native_manifest.csv`：原始纹理名、G1T/TEXINFO、平台格式、`ounce` swizzle、原始/输出尺寸、PNG/G1T SHA-256。
- `NativeCandidates/pokemon_native_summary.json`：PNG 数量、解码覆盖率、来源类别。成功解析 PNG 仍标记 `PNG_CANDIDATE_UNVERIFIED`，不能直接当成游戏最终显示验证。
- `pokemon_identity_crosswalk.csv`：逐条关联 KIDSOBJDB 的 `object_hash` / `objdb_file`、G1T/TEXINFO Hash、原生 PNG，明确 **`native_species_id_verified` 为空**。
- `pokemon_identity_summary.json`：独立记录 609 个纹理引用核验，`species_id_verified_count=0`。
- `NativeCandidates/contact_sheet_pokemon.png` 与 `contact_sheet_pokemon_uni.png`：抽样检查拼图。

## 必须区分的身份

1. `icon_poke_0082_00_00_00` 中的 `0082` 是原生纹理名称的一部分。它与某些图鉴编号可能一致，但 **不构成官方物种 ID 映射证据**。
2. `icon_poke_uni_XXXX` 与 `icon_poke_XXXX` 也不是可直接互换的类别；名称后面若出现形态/服饰等后缀，必须完整保留。
3. **6 条同名不同原始来源**各自保留 TEXINFO/G1T 双 Hash 作为唯一键，不能只按四位数字覆盖。
4. 要把 `native_species_id_verified` 填上，须从原生物种表、村民外观表或实际运行时纹理绑定调用找到 **同一条资源哈希**，再用游戏截图或确定身份的独立参考图验证；不能按序号、颜色、外形等推断并批量填充。

## 复现

```bash
python -m pip install "Pillow>=11,<13"
python -m Scripts.resources.export_native_pokemon_icons
python -m Scripts.resources.audit_native_pokemon_identity
```

导出会读取 2.0.1 的真实 `romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/`，校验 TEXINFO 数量、名称、UV、G1T 哈希/大小，并生成 PNG 与清单。CI 工作流：

- `.github/workflows/unpack-m5-pokemon-export.yml`：609 张源图导出和 SHA/PNG 校验。
- `.github/workflows/unpack-m5-pokemon-identity.yml`：KIDSOBJDB 关联、重复资源保留、物种 ID 不推断。

所有原始解包文件保持在 `UnPack/2.0.1/romfs/`；本目录只放可重复产生的派生图像和核验证据。
