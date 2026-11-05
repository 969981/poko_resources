# Pokopia 2.0.1 — M9 UI/素材批量 PNG 全透明记录复核

原版 `UnPack/2.0.1/romfs` 的 KIDSOBJDB TEXINFO→G1T 3,930 条唯一索引边全部成功解码并导出 PNG。合并报告 `native_misc_png_summary.json` 记录 3,925 条 `PNG_CANDIDATE_UNVERIFIED` 与 **5 条 `TRANSPARENT_CANDIDATE_REVIEW`**；这里的透明是原始 UV 裁出的 Alpha 全零，不是 PNG 文件读取失败。

| 批次 | TEXINFO 原生 sprite 名 | TEXINFO Hash | G1T Hash | 原生 record/layer | PNG |
| --- | --- | --- | --- | --- | --- |
| 08 | `0300_base_character_table` | `92c1f2f7` | `f08014c2` | 0 / 0 | 4×4、Alpha 非零 0 |
| 11 | `0000_prt_square_transparent` | `987344aa` | `bc2c37f5` | 376 / 31 | 4×4、Alpha 非零 0 |
| 15 | `icon_skill_005` | `f552e8cf` | `24e5b69a` | 366 / 3 | 4×4、Alpha 非零 0 |
| 15 | `icon_skill_009` | `f552e8cf` | `24e5b69a` | 370 / 3 | 4×4、Alpha 非零 0 |
| 15 | `icon_skill_010` | `f552e8cf` | `24e5b69a` | 371 / 3 | 4×4、Alpha 非零 0 |

5 张均使用真实 TEXINFO 原始 UV 和 Ounce 解码，各张 PNG 的 SHA-256 为 `6fa466e21df6bf014ed03517399a711777f572b1f0be6a561b947790cda9f634`。这仅说明裁得同样的透明 RGBA 4×4 结果。原始关联、记录位置及 G1T SHA 仍保存在各 `MiscNativeBatches/batch_XX/misc_native_sample_manifest.csv`。

**解释限制**：`square_transparent` 名称看起来是透明占位符，技能图标可能是不存在/未启用的槽位，但**没有游戏运行时显示验证**，不能直接删除这些纹理、推断它们必然不可使用，或将其与其它材质共享对象合并。状态保留 `TRANSPARENT_CANDIDATE_REVIEW`；所有 5 条仍计入“3,930 条成功 PNG 导出”和“需复核像素内容”。

验收文件：

- `native_misc_png_catalog.csv`：3,930 条唯一记录的 PNG/原始路径/层/UV、哈希和状态。
- `native_misc_png_summary.json`：17 批全部存在，`missing_source_records=0`，`recorded_failure_rows=0`。
- `native_misc_texture_summary.json`：其它 418 条未建立可唯一验证的原生关联（368 原始 G1T 找不到或歧义、50 索引边歧义）继续单独追查。

不能把“3,930 条 PNG 可解码”误写为“3,930 张游戏屏幕中都确实显示且逐像素一致”。
