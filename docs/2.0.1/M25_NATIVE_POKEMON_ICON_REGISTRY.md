# M25 — 原生 KIDS 图标索引闭环、26 张补充 PNG、17 张村民头像恢复

> 游戏版本：Pokopia **2.0.1** · 分支：`2.0.1_unpack` · 证据边界：原始 ROMFS / root RDB/RDX / 已归档解码记录、KIDSOBJDB 原始二进制、ExeFS NSO0、原生 G1T/TEXINFO、PNG 字节。  
> 所有数值均有脚本和 GitHub Actions 复现，**图像高度相似 ≠ 游戏原生物种或村民 ID 已证明**。

关联：[[M24_KIDS_GENERIC_REGISTRY_AND_ID_ANCHORS]] · [[M23_FDATA_PLATFORM_AND_KIDS_CONSUMER]] · [[M22_VILLAGER_NATIVE_SOURCE_AUDIT]] · [[M21_NATIVE_AUX_ICONS]]

## 1. 当前成果与正式剩余任务

| 范围 | M21 初始状态 | M25 当前状态 | 验证口径 |
| --- | ---: | ---: | --- |
| PokoHex 村民头像参考文件 | 378 | 378 | 第三方参考来源未改动 |
| 对应原生图像且视觉区分明显 | 290 | **307** | 原生 G1T/TEXINFO→PNG 与严格图像距离校验，仍非运行时 ID 绑定 |
| 尚无可靠匹配的头像 | 79 | **62** | 连续 PokoHex 肖像 ID 317–378 |
| 多个候选尚未确定 | 9 | **9** | 54 条候选已能回溯到 KIDS 原生数组槽位 |
| M25 新解码原生 PNG | 0 | **26** | 17 个常规图标 + 9 个 `icon_poke_uni_` |
| 正式游戏原生物种 ID 绑定 | 0 | **0** | 尚无同一实例游戏 ID → 源对象 → 纹理消费者证据 |

[更新后的 378 项村民来源清单](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_6_complete_378_villager_candidate_inventory.csv) · [当前覆盖汇总](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_6_complete_villager_coverage_summary.json)。

已将新增 17 张源文件字节核对后的 PNG 复制到现有 [Villagers/Native_2.0.1/Icons](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/Icons)，合计 **307 张实际 PNG**。M21 基线文件未被覆盖，M25 单独维护合并版清单。

## 2. M25.0 — 原生 KIDS 第二跳发现

此前 M19 已确认 603 条：
**Source OID → 属性 `0x2856A1B3` → Texture OID → G1T/TEXINFO Hash**，但没有人知道哪些原生表使用 Source OID。

本轮以全部 603 个 Source OID 为目标，在原始 `0xacd220a8.fdata` 的 **678/678** 份 KIDSOBJDB 中逐一解析所有 IDOK 有类型的 u32 标量/数组（共 **962,158** 项），找到 **603** 次原生字节引用，覆盖全部 603 个 Source OID。

关键主表来源：

| 项目 | 原生证据 |
| --- | --- |
| 源文件 | `root_019167_50ae86ef.kidsobjdb` |
| SHA-256 | `86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541` |
| 原生数组对象 OID | **`0xB4A1803B`** |
| 对象 Type Hash | **`0x9D1AFA46`** |
| 数组属性 Hash | **`0x34CBB458`** |
| 原始数据类型、总项数 | 原生 kind=5、**3,543 × u32** |
| 数组第 0 项原始字节偏移 | **378728** |
| 宝可梦常规图标区域 | **429–742（314 个槽位）** |
| 宝可梦 `uni` 图标区域 | **743–1056（314 个槽位）** |

主表中有 602 个槽位直接引用已经验证的 Source OID。另有独立对象 OID `0x15ADF4B3`（同一 Type Hash `0x9D1AFA46`），其 **15 项数组的索引 10** 引用 `icon_poke_at_home` 对应 Source OID。该来源不应并入主表 628 个槽位。

**重要限制：** 这里的 314 × 2 是**资源数组索引区段大小**，不是原生图鉴/物种总量。不能直接设 `species_id = slot - 429` 或 `slot - 743`。

原始 M25 证据：[603 条第二跳字节引用](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_original_second_hop_kids_source_oid_backrefs.csv) · [解析计数](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_original_second_hop_summary.json)。

## 3. M25.2–M25.4 — 26 个图标槽位为何曾被遗漏？

主表的 628 个槽位中，最早只匹配到 602 个，另有 **26 个“未命中已知 603 个源对象”的索引槽位**。本轮对其原始字节回读，得到：

1. **26/26 数组原始值均是存在的 Source OID**，不是 0 或空占位；
2. **26/26 Source OID 均具有原始 `0x2856A1B3` typed u32 字段**，且指向真实存在的 Texture OID；
3. **26/26 Texture OID 均有非零 G1T 和 TEXINFO Hash**；
4. 26 个 G1T 的原生 `.g1t` 文件全都已在 Git 中，TEXINFO 只有 `.texinfo` 扩展名文件缺失；
5. 再查原始 root RDB 发现：**26 TEXINFO 和 26 G1T 原始记录全属于 `0x00011c54.fdata`（raw platform `FFFF`）**，不仅原始物理 FDATA 已归档，而且 26 个 TEXINFO 的 **解码 `.fdata_idrk.bin` 也已发布**。

因此，这 26 个资源的遗漏原因是 **TEXINFO 原生后缀重建／贴图输出流程漏覆盖**，不是缺少 FF03 平台的原始 ROMFS，不应该再让用户上传这 26 个已有文件。

实例：主表 `slot 455`：
- Source OID `0x06AB845F`，Texture OID `0xC1A6D60C`；
- G1T Hash `0xAB6768BD`，原生 `root_040595_ab6768bd.g1t`；
- TEXINFO Hash `0x2198D172`，已有解码 `root_008079_2198d172.fdata_idrk.bin`；
- 原始 TEXINFO 文本确实是 **`icon_poke_0043_00_00_00`**，不是仅靠两侧 `0042/0044` 推测；图层 0，UV `0,0 → 0.609375,0.609375`；
- 平台 `0x18`、BC7 (0x66)，原生 PNG 裁剪结果 156×156。

可逐项查：
- [628 个原生槽位原始字节表](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_2_full_628_native_icon_registry.csv)
- [26 项完整 Source/Target/G1T/TEXINFO Hash](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_3_26_original_source_to_texture_objects.csv)
- [52 条原始 RDB 来源记录与解码文件路径](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_4_26_texture_hash_rdb_provenance.csv)

## 4. M25.5–M25.6 — 真正批量恢复原生 PNG 与村民匹配

对 26 份已有解码 TEXINFO 和 26 份原始 G1T 做稀疏签出，逐项恢复 TXTINFO 名称、UV、原生图层和 BC7，使用已验证的 Ounce GOB 排列解码 PNG 并做 SHA256。

结果：**26/26 PNG 成功，26/26 具有非透明像素，0 原生解码失败。**

[原生 26 张 PNG、联系表、完整来源清单](../../UnPack/2.0.1/Resources/Pokemon/NativeRecoveryM25)

将新图像与前一阶段**79 张真正未匹配**的 PokoHex 参考肖像重新进行 Alpha-aware 32×32 MAE，采用原 M21 保守阈值 + 与第二近候选和历史最近候选的区别验证，新增 **17 个高置信视觉候选**：

| PokoHex 参考肖像 ID | 经原始 TEXINFO 确定的纹理名 |
| ---: | --- |
| 28 | `icon_poke_0043_00_00_00` |
| 38 | `icon_poke_0053_00_00_00` |
| 46 | `icon_poke_0063_00_00_00` |
| 62 | `icon_poke_0083_00_00_00` |
| 66 | `icon_poke_0093_00_00_00` |
| 77 | `icon_poke_0109_00_00_00` |
| 81 | `icon_poke_0122_00_00_00` |
| 89 | `icon_poke_0132_00_00_00` |
| 95 | `icon_poke_0142_00_00_00` |
| 115 | `icon_poke_0172_00_00_00` |
| 144 | `icon_poke_0240_00_00_00` |
| 258 | `icon_poke_0739_00_00_00` |
| 270 | `icon_poke_0838_00_00_00` |
| 271 | `icon_poke_0841_00_00_00` |
| 275 | `icon_poke_0910_00_00_00_nh` |
| 276 | `icon_poke_0917_00_00_00` |
| 279 | `icon_poke_0920_00_00_00` |

这些视觉匹配差异约为 **0.00033–0.00305**，全都达到独立最优候选和更强区分门槛。**这些是参考肖像 → 原生 PNG 的强证据，尚不能写成 runtime 村民 ID=纹理编号。**

资源与证明：
- [26 张 PNG 的逐项原生来源 SHA/UV/名称](../../UnPack/2.0.1/Resources/Pokemon/NativeRecoveryM25/m25_5_native_icon_export_manifest.csv)
- [79 张参考头像的重新匹配和距离](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_5_79_portrait_visual_crosscheck.csv)
- [378 项更新后的村民来源总清单](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_6_complete_378_villager_candidate_inventory.csv)

## 5. M25.8 — 原生图标对象来源索引已经覆盖本批 **629 个**已识别 Source OID

把旧的 603 个和新解码的 26 个 OID 合并到同一份来源清单：

| 原始 KIDS 来源 | 已验证 Source OID | 已验证 Target Texture OID |
| --- | ---: | ---: |
| 常规图标数组 429–742 | 314 | 314 |
| `uni` 图标数组 743–1056 | 314 | 314 |
| 单独 `icon_poke_at_home` 数组 | 1 | 1 |
| **总计** | **629（互不重复）** | **629（互不重复）** |

全部 629 项都有已建立的原生 PNG 路径；其中原先 603 项保留 M16/M19 来源，26 项保留 M25 解码的新证据，不因同名 PNG 或 PokoHex 名称自动合并不同 Source OID。

[完整 629 项原生图标对象与纹理清单](../../UnPack/2.0.1/Resources/Pokemon/NativeRecoveryM25/m25_8_complete_native_629_kids_icon_source_index.csv)。

**629 是已研究的原生图标来源对象数量，不是宝可梦物种总数或村民总数，也不等于独立图像名称数量。**

## 6. M25.7 / M25.9 — 原生消费者与 9 张歧义图的新进展

ExeFS 原始 NSO 中已有：

- 属性 Hash `0x34CBB458` 的原始 rodata u32 常量单元：**`main+0x283883C`**；
- 数组对象 Type Hash `0x9D1AFA46` 的三个 `movz/movk` 候选：
  - `main+0xBE19C8 / 0xBE19D0`，随后尾部分支到通用函数 `main+0x1FDC1E0`；
  - `main+0xBE1A54 / 0xBE1A5C`，随后也进入同一通用函数；
  - `main+0xDD1C30 / 0xDD1C34`，原生相邻指令直接构造并返回 `0x9D1AFA46`。
- 这些可说明此类型进入了原生注册/类型标识路径，**但并未证明哪个游戏 ID 作为 3,543 项数组的索引**。
- 对 9 张多候选 PokoHex 肖像 ID（16、18、96、98、218、220、296、297、298），其 **54 条原生 Source→Target 资源边已全部连接到原始数组槽位**，现在可精确区分每个候选的数组位置、源对象和目标纹理 Hash，但仍不能自动判断游戏某个村民的最终外观。

资料：
- [原生 NSO 属性 Hash 寻址与反汇编](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_7_original_registry_hash_assembly.json)
- [9 张歧义图 54 项原生数组槽位档案](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M25/m25_9_nine_ambiguous_native_array_slot_dossier.csv)

## 7. 可重复执行的脚本 / Actions

源脚本均在 `Scripts/resources` 中：

- `m25_original_source_oid_second_hop.py`：扫描 678 原始 KIDSOBJDB 和 962,158 原生 typed u32；
- `m25_2_original_icon_array_gaps.py`：从原始数组恢复 26 个遗漏 Source OID；
- `m25_3_recover_unknown_icon_object_targets.py`：26 条 source→target 及 G1T/TEXINFO Hash；
- `m25_4_missing_texinfo_rdb_provenance.py`：52 项原始 RDB/FDATA/已发布解码文件交叉核对；
- `m25_5_recover_26_native_icon_png.py`：精准稀疏提取、BC7 PNG 与 79 张参考头像视觉核查；
- `m25_6_merge_17_villager_native_icons.py`：307/9/62 总清单与新增 17 PNG；
- `m25_7_native_registry_hash_code_consumer.py`：原始 ExeFS 类型注册 Hash 候选；
- `m25_8_complete_native_icon_registry.py`：314+314+1 的 629 原生对象来源总清单；
- `m25_9_nine_ambiguous_registry_dossier.py`：9 张歧义图和 54 个原生索引槽位。

自动复现：
- [M25 第二跳和 26 个对象恢复](https://github.com/969981/poko_resources/actions/workflows/unpack-m25-pokemon-id-source-oid.yml)
- [M25.5 26 个原生 PNG 恢复](https://github.com/969981/poko_resources/actions/workflows/unpack-m25-5-restore-native-icon-png.yml)
- [M25.6 307 村民图标来源整理](https://github.com/969981/poko_resources/actions/workflows/unpack-m25-6-merge-villager-icons.yml)
- [M25.7 原生代码消费者 Hash 查找](https://github.com/969981/poko_resources/actions/workflows/unpack-m25-7-kids-registry-consumer.yml)
- [M25.8 完整 629 图标 Source OID 清单](https://github.com/969981/poko_resources/actions/workflows/unpack-m25-8-complete-native-registry.yml)
- [M25.9 九个歧义 PokoHex ID 的原生槽位](https://github.com/969981/poko_resources/actions/workflows/unpack-m25-9-ambiguous-array-slots.yml)

## 8. 下一阶段真正还需要的身份与资源证明

**A. 原生 ID 绑定：** 静态分析或运行时回读一个明确的游戏 `species/villager ID` 如何索引 KIDS 主表 `0xB4A1803B` 的 `0x34CBB458` 数组，并得到 Source OID，再从 `0x2856A1B3` 链到 Texture OID 和 G1T。不能从文件名 `0043` 直接认定图鉴 43。

**B. 9 张歧义图：** M25.9 已保留 54 个有原生位置的候选，下一步要取得游戏中实际村民外观/形态的选择字段、消费者调用和实际数组索引；不可单纯按图像最近距离决定。

**C. 剩余 62 张肖像（第三方 ID 317–378）：** 它们在目前恢复的原生图标来源范围内没有可靠视觉对应。应核实 PokoHex 参考版本与 Pokopia 2.0.1 的 NPC/居民数据记录及版本差异，或继续查其它原生图像资源家族。**不能仅因连续缺失便断言“这是 DLC”或“原版没有这些宝可梦”。**

FF03 物理源容器缺失问题仍由 [[M23_FDATA_PLATFORM_AND_KIDS_CONSUMER]] 独立记录；**M25 已恢复的 26 个 PNG 无需 FF03 容器，来源全部是既有 `0x00011c54.fdata`**。

## M26 原生消费者与 62 张头像的最新验证（2026-11-05）

已继续推进到 [[M26_VILLAGER_ROSTER_AND_KIDS_PARALLEL_ARRAYS]]。M26.1 将剩余 62 张 PokoHex 参考肖像逐一与 629 个已验证原生 Source OID 对应的 635 张 PNG 做 SHA/图像对照，0 新增可靠匹配，因此保留 62 未定位、9 多候选；但并非证明游戏所有资源均缺失。对 9 张多候选取得 4 组互斥最优视觉方案，**不能当作运行时正式 ID**。

原生代码方面，M26.2/M26.3 从 KIDS 类 `0x9D1AFA46` 的 BSS 对象、安装的方法表 `main+0x33135C8`，定位到真实的属性枚举函数 `main+0xDD1B48`。它从 `main+0x2838834` 读取 `0x34CBB458`，并确认该类型有 **两个连续的 3,543×u32 数组**：`0xE88C8D60`（偏移 364556）和 `0x34CBB458`（偏移 378728）。M26.4 已导出所有 3,543 对原始值，第二数组中的 628 个图标 Source OID 逐项对账。第一数组的全部 3,543 个值均唯一且非零；常见直接名称 Hash 候选暂未命中，**原生物种 ID 到数组键/槽位的消费者还没有证明**。
