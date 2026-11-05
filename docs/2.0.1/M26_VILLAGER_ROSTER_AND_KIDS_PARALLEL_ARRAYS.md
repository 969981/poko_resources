# M26 — 62 张缺失头像、9 张多候选及 KIDS 原生双数组的证据链

> Pokopia **2.0.1** · 分支 `2.0.1_unpack` · 原生源文件 SHA-256、KIDSOBJDB typed 字段、原始 NSO0 指令、629 项来源图像全部可复验。  
> **严格区分**：第三方 PokoHex 身份数据、图像视觉候选、原生资源 ID、游戏运行时角色 ID。当前原生运行时 ID 绑定仍为 **0**。

相关笔记：[[M25_NATIVE_POKEMON_ICON_REGISTRY]] · [[M24_KIDS_GENERIC_REGISTRY_AND_ID_ANCHORS]] · [[M23_FDATA_PLATFORM_AND_KIDS_CONSUMER]] · [[M22_VILLAGER_NATIVE_SOURCE_AUDIT]]

## 1. 62 张参考头像的真实来源边界

原始 PokoHex 378 张 villager icon 中，M25 已恢复 307 张源数据明确且视觉高度相似的原生 PNG，另有 9 张多候选。**62 张未匹配集中于参考肖像 ID 317–378**。

交叉验证 `villager_catalog.csv`：

- PokoHex reference ID 317–378 之间 **每个 ID 恰对应 1 条**具有原生语言名称的第三方村民记录。
- 第三方 `villager_id` 在 **508–607** 范围，且这些记录 `is_public=1`。这仅是第三方数据字段，**不是 Pokopia 2.0.1 原生 ID 或内容发布证明**。
- 实例：317 Jirachi、318 Shellder、324 Totodile、340 Feebas、341 Milotic、347 Phione、348 Manaphy、357 Pumpkaboo、371 Applin、378 Hydrapple。
- PokoHex 还含部分没有肖像的其他参考记录，不能推测缺失的 62 张和这些记录同源。

[M26 62 张第三方参考头像逐项清单](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26/m26_62_third_party_portrait_roster.csv)

## 2. M26.1：对整个已验证的本组原生 KIDS 图标索引做负证据核验

从 M25.8 的 **629 个原生 Source OID** 到现有原始 TEXINFO/G1T PNG，可得到 **635 个有独立来源路径的 PNG**（609 个原有 +26 个 M25 新解码）。本轮对全部 635 个 PNG 逐项检查 SHA256，然后对 62 张第三方头像以 Alpha-aware 32×32 MAE 进行原样全量对比：

| 项目 | 结果 |
| --- | ---: |
| 原生 Source OID | 629 |
| 有 SHA256 原始凭据的源 PNG | 635/635 |
| 检查的第三方头像 | 62/62 |
| 新的可靠视觉相似候选 | **0** |
| 本组 629 Source OID 内仍未匹配 | **62** |

置信门槛：归一化 MAE ≤0.015，同时与另一独立 Source OID 候选分离 ≥0.015。

**准确的负结论**：这 62 张在已恢复的此组 629 个 KIDS 图标来源对象中没有可靠视觉匹配。**不能推断它们在 Pokopia 2.0.1 其他原始容器中不存在**；M23 的 FF03 物理 FDATA 缺失和其他图像家族仍需独立查证。

[62 项原始全量视觉证据](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26/m26_1_62_vs_complete_629_icon_registry.csv) · [M26.1 汇总](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26/m26_1_original_icon_registry_negative_audit.json)

## 3. 九张多候选：M26 约束唯一的视觉候选，但仍不等于原生游戏 ID

M25.9 已为 9 个 PokoHex 参考头像保留 54 条 Source OID→Texture OID→G1T/TEXINFO 的逐字节原始资源引用。M26 再从同一纹理家族中筛出相关**常规头像**，对槽位做一对一、不重复的最低总视觉误差分配：

| 参考肖像 ID | 优先数组槽位（按参考 ID 顺序） | 最优总 MAE | 次优总 MAE |
| --- | --- | ---: | ---: |
| 16 / 18（皮卡丘特别外观） | 445 / 444 | 0.00252566 | 0.00553768 |
| 96 / 98（卡比兽特别外观） | 524 / 523 | 0.00528301 | 0.00739507 |
| 218 / 220（巨蔓藤特别外观） | 645 / 644 | 0.00610064 | 0.00884842 |
| 296 / 297 / 298（米立龙三个形态） | 721 / 722 / 723 | 0.00308479 | 0.02401387 |

**此表只是优先调查顺序**：前三组次优差距较小，即使一次一对一视觉组合最优，也不能证明游戏运行时根据什么字段选中哪一张图；不写 `native_species_id_verified` 或正式村民 ID 映射。

[9 张优选视觉候选](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26/m26_9_visual_only_disjoint_slot_assignments.csv) · [4 组的最优与次优](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26/m26_4_visual_variant_group_alternatives.csv)

## 4. M26.2/M26.3：从原生 BSS 类到 3 项属性描述器的真正调用链

KIDS 原始对象：`root_019167_50ae86ef.kidsobjdb`，SHA256：

`86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541`

原始 NSO `2.0.1/exefs/main` SHA256：

`8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`

静态原始代码和数据共同确认：

```text
main+0x349C2E0 -> main+0x367AD40       # BSS 原生类型对象
main+0x349C2E8 -> main+0x33135B8       # 方法表原始指针
main+0xBE1A24: add x8,x8,#0x10
main+0xBE1A28: stp x8,x9,[x1]          # 静态安装 VTable +0x33135C8

[main+0x33135C8 +0x18] -> main+0xDD1B48
[main+0x33135C8 +0x28] -> main+0xDD1C30  # 返回 Type Hash 0x9D1AFA46
```

**核心突破：`main+0xDD1B48` 确实执行原生属性描述器索引与数据读取，而不只是一个孤立的常量引用。**

```asm
main+0xDD1B50  cmp w3,#2                ; 原生属性描述器索引范围
main+0xDD1B58  adrp x8,#0x2838000
main+0xDD1B5C  add x8,x8,#0x828        ; 属性元数据数组
main+0xDD1B60  adrp x9,#0x2838000
main+0xDD1B64  add x9,x9,#0x834        ; 属性 Hash 数组
main+0xDD1B68  adrp x10,#0x3331000
main+0xDD1B6C  add x10,x10,#0x810      ; 相关原生指针数组
main+0xDD1B70  ldr w11,[x8,w3,sxtw #2]
main+0xDD1B74  ldr w12,[x9,w3,sxtw #2]
main+0xDD1B78  ldr x13,[x10,w3,sxtw #3]
main+0xDD1B7C  stp w11,w12,[x1]        ; 回写描述器的元数据及 Hash
main+0xDD1B88  stp x13,x11,[x1,#8]
```

这三项 Hash 与原生 KIDSOBJDB 的同类型对象完全对应：

| 描述器索引 w3 | 原始属性 Hash | 原生字段类型 | 原始数组元素 |
| ---: | --- | --- | ---: |
| 0 | `0x2F610FEA` | kind=5 u32 | 1 |
| 1 | `0xE88C8D60` | kind=5 u32 | **3,543** |
| 2 | `0x34CBB458` | kind=5 u32 | **3,543** |

这里 `w3=2` 是属性描述器索引，**绝不是游戏物种 ID=2**。

[原生 VTable/类实例证据](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26/m26_2_class_methodtable_descriptor_evidence.json) · [三属性原生 NSO 读取与原始对象核验](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26/m26_3_three_original_property_descriptors.json)

## 5. M26.4：两条 3,543 项数组构成逐位置对应的原生双数组

双数组皆在同一个原始 KIDS Source OID `0xB4A1803B` 中，字段数皆为 3543：

| 字段 | 原始 Hash | 原始数据起始字节偏移 | 有效长度 |
| --- | --- | ---: | ---: |
| 第 0 个单值属性 | `0x2F610FEA` | 364552 | 1 × u32，原始值 0 |
| 第一数组 | `0xE88C8D60` | **364556** | 3,543 × u32 |
| 第二数组 | `0x34CBB458` | **378728** | 3,543 × u32 |

**数组完全首尾相接**：`364556 + 3543 × 4 = 378728`。同一位置的两项原始 u32 可一一对照。第二数组中已经确认：

- **628 个位置**匹配 M25.8 的原始 KIDS 图标 Source OID（常规 314 + uni 314）；
- 两组数组中的 **各 3,543 个值都不重复，且都非零**；
- 第一数组的全部值都大于 1000，因此不是直接存储了 `0–1000` 这类普通整数物种编号。
- 针对原始图标名称与这批第一数组数据执行 **19,020 次候选 Hash 对账**：CRC32、FNV-1、FNV-1a、DJB2、SDBM，加上 ASCII/大小写/UTF-16LE/扩展名等常见变体，目前 **没有找到精确一致的算法**。

两个字段可能构成“键→对象 OID”索引，但**没有原生消费者调用证明第一数组确切表示资源名称 Hash，也没有确认哈希算法**。不能把它转写成正式物种列表。

[逐字节对账的 3,543 对原生数据](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26/m26_4_original_3543_parallel_key_value_pairs.csv) · [数组唯一性及 Hash 假设校验报告](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M26/m26_4_parallel_arrays_analysis.json)

## 6. 可复现自动化

代码均在 `Scripts/resources/`：

- `m26_villager_roster_variant_assignment.py`：62 条原始参考清单与 9 头像互斥视觉拟合；
- `m26_1_native_registry_full_negative_audit.py`：629 对象/635 PNG 与 62 肖像全量对照；
- `m26_original_icon_registry_consumer_trace.py`：原生 typehash、BSS 全局和 rodata 的精确候选；
- `m26_2_kids_class_descriptor_ownership.py`：原生方法表安装与描述器地址；
- `m26_3_kids_three_property_descriptor.py`：从 `main+0xDD1B48` 三描述器机器码连接 KIDSOBJDB 字段；
- `m26_4_parallel_3543_key_value_arrays.py`：两条原始 3543 长数组逐项对账、常见 Hash 假设审计。

所有研究均保留来源 SHA 和“原生 ID 未验证”的失败关闭条件。源码/结果未修改任何原始 ROMFS 字节。

成功的 GitHub Actions：
- [M26 62 参考与 9 候选审计](https://github.com/969981/poko_resources/actions/workflows/unpack-m26-villager-roster-variants.yml)
- [M26.1 全 635 PNG 对照](https://github.com/969981/poko_resources/actions/workflows/unpack-m26-1-native-registry-negative-audit.yml)
- [M26 原生 class/hash 入口](https://github.com/969981/poko_resources/actions/workflows/unpack-m26-icon-class-consumer.yml)
- [M26.2 VTable 与描述器源字节](https://github.com/969981/poko_resources/actions/workflows/unpack-m26-2-kids-class-descriptor.yml)
- [M26.3 三属性读取](https://github.com/969981/poko_resources/actions/workflows/unpack-m26-3-schema-3543-array.yml)
- [M26.4 并行数组原始数据](https://github.com/969981/poko_resources/actions/workflows/unpack-m26-4-parallel-kids-key-value.yml)

## 7. 后续突破口

**优先原生双数组消费者**：从 `main+0xDD1B48` 被哪个逻辑读取三属性描述器开始，追踪对 `0xE88C8D60` 键数组、`0x34CBB458` OID 数组的成对访问，恢复“原生键 → Source OID”的实际查询函数。再追该查询函数输入的游戏真实物种 ID 或实际游戏内部键，最后绑定到 628 个已验证图标对象。

**9 张特别外观**：如果查询函数确认游戏按物种/形态输入分别选到不同键，利用 M26 的 445/444、524/523、645/644、721/722/723 槽位做双向核验；在这之前只保留视觉优选。

**62 张缺失头像**：重点确认这批 PokoHex 参考条目在原始 2.0.1 的平台/补丁/附加内容表中是否存在，且与 M23 FF03 的缺失容器划清原始数据范围。不可因参考 ID 连续或游戏内字段公开，就宣布某个 DLC 日期、补丁缺图或官方尚未存在的角色。

## M27 原生数组数字 Hash 的下一阶段

参见 [[M27_ORIGINAL_KIDS_REVERSE31_NUMERIC_HASH]]。原始 KIDS 双数组的 626 项数字化图标数据（常规+uni）可被 31 多项式与四位编号字符逆序模型全部精确预测，其中 612 条为每组首样本之外的独立留出对账；14 个组中 4 组只有一例，不宣称通过独立验证。枚举 14×10,000 个候选未在原始 3543 双数组中发现新的非 M25 图标对象。**仍需从游戏 ExeFS 实际实现验证算法，并证明运行时游戏 ID→原生键/OID 的消费者调用链。**


## M31 类型和资源包装层新证据

现在已经恢复 `0x9D1AFA46` 的原始类名 `ScreenLayoutTexturePackSettings`、`0x79991E79` 的原始类名 `StaticScreenLayoutTextures`；后者的 `0x2856A1B3` 字段真实名称是 `WrapStaticScreenLayoutTexturesObjectHash`。M31.5 原始源文件逐字节确认 **628/628** 个索引对象都经过**包装 IDOK 对象**，该包装对象才保存匹配 M25 索引的 G1T/TEXINFO 文件 Hash。这是资源端闭合，不代表角色 ID→数组键消费者已找到。详细见 [[M31_KIDS_TWO_HOP_SCREENLAYOUT_TEXTURE_PROVENANCE]]。
