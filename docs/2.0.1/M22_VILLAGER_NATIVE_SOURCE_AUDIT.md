# M22 — 村民头像剩余 79 张来源搜索与 9 张变体原生引用

> 分支：2.0.1_unpack；源：原始 2.0.1 ROMFS、原始 KIDSOBJDB 二进制、M17/M19 字节验证图与 M21 图像清单。本笔记属于 source-qualified 资源研究，不声称已恢复原生村民物种 ID。

关联：[[M21_NATIVE_AUX_ICONS]] · [[M20_NATIVE_SPECIES_ITEM_CALLGRAPH]] · [[FULL_UNPACK_STATUS]]

## 1. 目标拆解和实测

M21 的 378 张 PokoHex 参考村民头像中，290 张具有高度区分的原生图像候选，88 张不满足严格的 M21 视觉判定阈值。

| 未匹配组 | PokoHex 肖像 ID | 数量 | 结论 |
| --- | --- | ---: | --- |
| 大段连续缺失 | 317–378 | 62 | 同一段编号连续未命中原生 609 张图，疑似输入覆盖/版本/独立资源分组问题；具体原因未证明 |
| 零散缺失 | 28、38、46、62、66、77、81、89、95、115、144、258、270、271、275、276、279 | 17 | 仍找不到高区分度的原生像素候选 |
| 多个形态相似候选 | 16、18、96、98、218、220、296、297、298 | 9 | 视觉差距不足，但每个候选都已有原生资源 Hash 与类型字段引用 |

完整 PokoHex ID / 名称 / 2.0.1 原生来源查询入口：

- [79 项目标及游戏名](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M22/m22_unresolved_79_source_targets.csv)
- [9 项所有备选、纹理 Hash、源码对象引用地址](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M22/m22_nine_ambiguous_native_object_refs.csv)
- [9 项原生类型引用汇总](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M22/m22_nine_typed_reference_summary.json)
- [79 项在 3,930 张原生非宝可梦图像中的前 3 候选](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M22/m22_79_other_native_png_top3.csv)
- [审计总账](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M22/m22_summary.json)

### M22 的独立检索边界

已在 17 个原生杂项纹理批次中检查 **3,930/3,930** 张已有 TEXINFO→G1T→PNG 来源的图像，对前述 79 张头像进行 32×32 Alpha-aware 视觉搜索。结果：**没有出现满足保守阈值及次优差距的额外原生头像候选**。

这是一条有范围的负结果，只覆盖已解码的 3,930 张其它 PNG，不代表游戏完整 ROMFS 内不存在这些头像。所有候选都记在 CSV，不能把非零但最高的相似度叫作“已恢复原生头像”。

## 2. 原生字节引用：9 张歧义头像

真实 KIDSOBJDB 来源：

`UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0xacd220a8.fdata/native/root_019167_50ae86ef.kidsobjdb`

经 M19 原生 Hash 边和 M22 再验证，9 张参考头像的 54 条变体候选都可回读源码，满足：

- 对每条记录重新 SHA-256 校验整个原始 .kidsobjdb；
- 对每条源对象读取属性 Hash `0x2856A1B3` 的原始字节偏移；
- 原始小端 u32 值等于目标 Texture Object Hash；
- 目标 Texture Object 上记录的 G1T/TEXINFO 属性 Hash 分别与对应实际 PNG 的来源一致。

**本阶段补的是 source object → target texture object → G1T/TEXINFO 的原始资源关系，不是 game villager ID → sprite 的原生语义关系。**

部分可独立复核的真实偏移：

| 参考身份组 | 原生 TEXINFO sprite 候选 | Source OID → Target OID | 原始源码属性 byte offset |
| --- | --- | --- | ---: |
| 浅浅丘 / Pikachu 变体 | icon_poke_0025_00_00_00_nh | 933637c2 → d3fc50c9 | 302424 |
| 苔卡比兽变体 | icon_poke_0143_00_00_00_nh | a08691e5 → 28ceecc6 | 325680 |
| 巨蔓藤博士变体 | icon_poke_0465_00_00_00_nh | ca346742 → 9bbe7149 | 434728 |
| 米立龙外观 11 | icon_poke_1056_11_00_00 | c7b64d5e → 35b429ad | 429832 |
| 米立龙外观 12 | icon_poke_1056_12_00_00 | 8ec2345f → d222260c | 294288 |
| 米立龙外观 13 | icon_poke_1056_13_00_00 | 55ce1b60 → 6e90226b | 173616 |

其余候选及第二版本使用独立 Object Hash 和 source-original-offset，不因 sprite 同名或内容相似而去重。特别是 `_nh`、普通和 `uni` 版本：即使内容非常接近，也有不同原生对象来源。M22 无法证明“肖像 ID 16 对应哪一个原生记录”这类最终语义，必须继续查 gameplay consumer。

## 3. 缺失物理输入的类型审计

全 ROMFS 输入覆盖来自 [source_coverage.json](../../UnPack/2.0.1/_reports/source_coverage.json)：缺少 27 个物理文件，影响 6,118 条原始索引记录。类型哈希使用 `Scripts/unpack/m3_types.py` 的定义：

| 推断原生格式 | 类型 Hash | 缺失记录 |
| --- | --- | ---: |
| G1T | afbec60c | **557** |
| KTID | 8e39aa37 | **322** |
| TEXINFO | f20de437 | **12** |
| KIDSOBJDB | 20a6a0bb | **371** |

只看原始纹理候选，最有价值的缺失容器优先级是：

| 缺失原始容器 | G1T | KTID | TEXINFO | 说明 |
| --- | ---: | ---: | ---: | --- |
| 0xfd6af828.fdata | 294 | 133 | 0 | 首批核验源平台后补齐 |
| 0x03a38715.fdata | 227 | 180 | 0 | 首批核验源平台后补齐 |
| 0xb6a6f383.fdata | 16 | 5 | 0 | 次级 |
| 0x00184b41.fdata | 12 | 0 | 12 | 唯一缺失 TEXINFO 组 |
| 0x6e422233.fdata | 8 | 4 | 0 | 次级 |

`0x00184b41.fdata` 的 12 份缺失 TEXINFO 原始记录，其中 11 份索引申报未压缩 108 字节（1×104 字节记录 + 4 字节计数头），1 份 420 字节（4 条记录），总计**最多 15 个独立 TEXINFO 图块记录**。这不能单独解释 62 张连续缺失肖像，但 557 个未供给 G1T 的确需重新核验是否与已有 TEXINFO 有引用。

请勿把 platform_flags=ff03、fffe 直接理解为 Switch 2 实机必须加载：先从原始 RDB、平台枚举和游戏运行时路径证明，才能下结论。也不能把缺失 FDATA 中任一项指认为特定肖像的来源，因为目前没有每个肖像的直接原生路径。

详见：[按缺失文件列出的类型计数](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M22/m22_missing_texture_containers.csv) 和 [JSON 源覆盖报告](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M22/m22_source_coverage_summary.json)。

## 4. 重现与验证

`Scripts/resources/m22_villager_native_provenance.py` 只读源文件，按需要加载 609 张原生宝可梦图、3,930 张原生 UI 图、M19 已验证边和原始 KIDSOBJDB 二进制；原始资产不被改写。

```bash
python -m pip install "Pillow>=11,<13"
python Scripts/resources/m22_villager_native_provenance.py --self-test
python Scripts/resources/m22_villager_native_provenance.py --skip-misc
python Scripts/resources/m22_villager_native_provenance.py
```

GitHub Actions 自动再现：[M22 - Native villager source and variant reference investigation](https://github.com/969981/poko_resources/actions/workflows/unpack-m22-native-villager-provenance.yml)。

验收断言：88 = 79 + 9；79 = 62 + 17；M19 603 源类型对象边，9 组变体所有 source→target u32 都能从原始 SHA256 字节复核；3,930 杂项 PNG 全范围；缺失 TEXINFO 12 文件共 15 槽；**原生游戏物种 ID 验证计数 0**。

## 5. 下一步需要的原生消费者证明

1. 优先查 missing_input_records 与原始 RDB 中 G1T/KTID 的跨文件 Hash 引用，找出可证明与现有 TEXINFO 绑定的缺失 G1T；核实平台后补全原始物理 FDATA，重新跑 M0/M2/M3/M5/M22。
2. 对 62 张连续缺失（317–378），从 PokoHex 的 villager_portrait.bin 出发只作为第三方候选 ID；回查 2.0.1 原生村民/外观表是否实际包含这些游戏 ID，再决定是否为版本差异或输入覆盖问题。当前暂不能证明任一种解释。
3. 对 9 张歧义对象，沿已确认的 source_oid→target_oid 引用，进一步定位构造/消费者对 `0x2856A1B3` 的语义，并建立 **game villager ID → source object → target texture OID** 全链，再以运行时头像读取验证。
4. 保留所有无法证明身份的候选；不以距离接近、Hash 邻近或数字相同直接写到 `native_species_id_verified` 等正式字段。

## M23 / M23.1 追踪进展（2026-11-05）

继续研究见 [[M23_FDATA_PLATFORM_AND_KIDS_CONSUMER]]：原始 RDX 已确认 FF03 的 10 组资源均未在当前仓库归档；目标 521 条 G1T 在现有三个纹理索引无直接 Hash 命中。原生 ExeFS 已进一步验证 `main+0xBB85CC` 的方法表安装路径、位于 BSS 的静态对象地址 `main+0x366E6F0` 与 `0x79991E79` 类型常量。该结果仍不是正式物种/村民 ID 绑定，9 张歧义图仍保持未验证。
