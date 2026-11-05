# Pokopia 2.0.1 — 物种 ID 与物品材料类型证据计划（M9）

## 目的与不可跨越的边界

本阶段有三个相互独立的目标：

1. 从**原生代码/表的实际消费者**证明 `species_id → sprite_name / TEXINFO/G1T hash`，而不是仅使用图像相似或 `icon_poke_XXXX` 中的数字。
2. 从 2.0.1 原始 `00983.bin` 每条 **68 字节物品记录**找到能证明其物品类别、原料/非原料归属的字段及枚举取值；借由独立的原生调用者或结构定义恢复语义。
3. 对 3,930 条已具唯一 TEXINFO/G1T 索引边的 UI/素材/场景纹理，分批真实解码、保留 418 条未定位/歧义记录并逐项复核，而不是只输出 PNG 总数。

三项工作可能需要不同原始表和 ExeFS 反汇编，**不能**把“关联了 KIDSOBJDB”解释为“物种 ID/材料 ID 已确定”。

## A. 原生宝可梦 ID 对照的验证路径

现有输入：

- `Resources/Pokemon/pokemon_texture_index.csv`：609 条原生纹理元数据（原始 TEXINFO 记录名、表内 index、UV、层、G1T hash）。
- `Resources/Pokemon/pokemon_identity_crosswalk.csv`：609 条唯一 KIDSOBJDB Hash 引用 + 609 张经过 Ounce 修正的 PNG。
- `Resources/Villagers/villager_catalog.csv`：PokoHex 村民名称、`villager_portrait.bin` 的 **raw portrait ID**。此值目前没有被原生 2.0.1 表证明等于宝可梦物种 ID。
- `Resources/Localization/M8`：物品/地图组件文本引用和角色反应/技能的原生引用证据；它尚未证明宝可梦物种纹理身份。
- 2.0.1 原始 ExeFS `main` 与 LINKDATA、KIDSOBJDB、可能的 FlatBuffers/BFBS 结构资源。

核验顺序：

1. 在原版 ExeFS 里查找 `icon_poke_`、`icon_poke_uni_`、格式化拼接逻辑及取纹理的 Hash 函数；静态记录调用者、交叉引用、实际输入寄存器/对象来源。仅仅查到字符串不够。
2. 从纹理加载路径向上回溯物种/形态/外观 ID 字段；如有 `species/form/gender/costume`，分别记录字段原始 offset、整数宽度、资源名生成规则，并验证至少两组不同形态及一组同名多 Hash。
3. 对照原生物种或村民信息表的同一条记录，证明传入纹理加载器的字段属于物种 ID；最好用实际游戏中显示的图标再交叉验证。PokoHex/全国图鉴数字只作为辅助，不是原生证明。
4. 写 `source_record, field_offset, raw_id, sprite_name, texinfo_hash, g1t_hash, original_offset, runtime_or_static_xref, evidence_grade`；无法证明 ID 就维持 `native_species_id_verified=""`。
5. 核对 `icon_poke_uni` 与 `icon_poke` 是否使用同一个消费端；不可以假定两者是同一字段的不同尺寸。

**验收门槛**：不是“609 个文件名编号相同”，而是至少 3 个真实、可复现的原生消费者回溯样本（跨普通/UNI/形态），随后扩充、处理重复资源哈希冲突，且每条经确认的 ID 都有原始偏移和调用者证据。**当前已证明物种 ID 数量：0**。

## B. 原生物品 00983.bin 字段结构与材料分类

原始输入：`UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin`；头 64 字节、`u32 count=4600`、`u32 version=3`、`stride=68`；`record_offset = 64 + id*68`。已证明 `+0x22`（十进制 +34）是 `u16 name_index`，并在语言表 `04645.bin..04653.bin` 全部核对一致。除这个字段外，未得到可信任的语义 enum 结构。

**新候选线索**：在原始表中，`record+0x26`（十进制 +38）的一个字节在 `stone`、`iron ore`、`copper ore`、`glass` 等样本均为 `0x10`，料理样本多为 `0x0F`、种子常见 `0x0A`、家具出现多种其他值。该 byte 是强烈的“物品分组/使用类别候选”，**不是已证实的 `MaterialType` 枚举**。原生资源中原料、可食材料、可制作材料等集合可能交叉；一个单字段未必能表示全部材料身份。

研究流程：

1. 严格解析整条 68-byte record，并生成全部 4,600 项字段指纹：所有偏移原值、相邻 `u16/u32` 值、九语言名称索引、原始 offset、原表 SHA-256。不要硬编码该字段含义。
2. 统计每个候选偏移的离散度、空槽分布、跨不同物品组的共现；将 `+0x26` 作为优先分析，不要把字节 0x10 直接列为最终材料。
3. 静态跟踪 ExeFS 的物品资料读取/道具列表筛选/合成材料需求/仓库显示逻辑，通过字段加载的机器指令（偏移、数值比较或跳表）恢复**原生语义**。若有 FlatBuffers/KIDSOBJDB schema 直接指向 `ItemKind`，需实际引用同一张物品表、确认 ID 对应并验证。
4. 用原版游戏 UI 中可验证的材料/食品/家具样本测试**正例与反例**，包括 cave mushrooms / stone / copper ore / iron ore / tomato / cooked soup / wall / seed；对同名多 ID 检查原始 ID、变体和标志。
5. 验收后写 `material_status=CONFIRMED_NATIVE_TYPE` 并列出 `field_offset, field_width, raw_value, native_consumer_xref, source_sha`。证据未达到门槛则输出 `CANDIDATE_ONLY` 或 `UNKNOWN`，不导出“全部材料”。

**即时可推进**：用自动审计脚本导出每个 `00983.bin` 记录的字段值与分组频率，使下一阶段的原生消费端逆向工作有完整、可检索的证据链。

## C. 3,930 条 UI/素材分批 PNG 导出

数据输入 `Textures/Indexes/native_misc_texture_index.csv`：4,348 条非 item/pokemon TEXINFO；其中 3,930 条 `INDEXED_ORIGINAL_TEXINFO_G1T_PAIR`，另 368 `G1T_ABSENT_OR_AMBIGUOUS_IN_PRIMARY_PACK` 与 50 `MISSING_OR_AMBIGUOUS_KIDSOBJDB_INDEX_EDGE`，二者不能当成 418 个错误纹理。独立原生样本 25/25 条 PNG 已通过校验 `Textures/MiscNativeSamples/`。

- 把 3,930 条按源键 `texinfo_hash + record_index + g1t_hash + layer` 稳定排序，划分为可重跑的不重叠批次，单批上限建议 240。
- 首先执行 SHA/文件名/索引/层/原始 UV 检查，再读取 G1T header、Ounce swizzle 和 PNG；按原始 `category_candidate` 输出，有歧义保留，不要擅自覆盖相同纹理名称。
- 每批保存 `manifest.csv`、`summary.json`、预览拼图和 PNG，写原始 Hash/路径、record_index、UV、真实宽高、格式、SHA 和失败原因。对完全透明、未支持格式和无法解码者标记独立状态。
- 同名多来源不可覆盖；需要补来源路径 Hash 或原始包路径，不能仅按 `texture_name` 命名。
- 最终总账严格做 3,930 条源记录的集合对账：无重叠、无丢失、不混入未关联的 418 条；成功输出数不以工作流 success 代替，须读取各批 manifest 状态。
- 分类目前仅是纹理名启发式：`ui_icon`、`ui_gameplay`、`material_name` 等，并不能证明物品 `ItemType`。


## 已执行的原始 2.0.1 ExeFS 静态反查（2026-11-05）

- 原始文件 `2.0.1/exefs/main`：NSO0，源 SHA-256 `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`；各压缩段解压验证：text **41,194,624** 字节、rodata **11,402,740** 字节、data **2,760,384** 字节。
- `Scripts/resources/trace_native_species_item_callers.py` 已检查 text 的 **10,298,656 条 4 字节指令槽**，用 AArch64 ADRP+ADD 原始编码解算 rodata 字符串地址；捕获 **44 条候选字符串交叉引用**。输出 `Resources/Pokemon/NativeCallers/main_string_xrefs.json`，保留原始 PC、ADRP/ADD 指令字、目标字符串 RVA。
- 高价值下一跳（**地址为 ExeFS NSO text RVA，不是游戏运行时绝对地址**）：
  - `m_craftRecipeId`：RVA `0x${(6270468).toString(16)}`
  - `m_craftMainHelpPokemonKind`：RVA `0x${(6270728).toString(16)}`
  - `m_craftHelpTable`：RVA `0x${(6270796).toString(16)}`
  - `m_mainPokemonList`：RVA `0x${(6279528).toString(16)}`
  - `pokemon_dex_id`：RVA `0x${(18049700).toString(16)}`
- 可确认这些名称存在于原版 rodata 并被原版 text 指令引用，**但尚不等同于物种 ID → G1T/TEXINFO Hash 的直接调用链**。
- 此版没有检测到包含 `icon_poke_` 的原始可打印字符串，可能是资源中名称生成/哈希加载，并不证明“没有该功能”。不能仅用字符串缺失下定论。
- 在 text 中也找到若干 `ldrb [Xn,#0x26]` 候选指令，但它们目前只证明代码里存在相同**位移**，还没有证明基址寄存器确实指向 00983.bin 的 68 字节 `Item` 记录；不得据此把原料枚举标为已恢复。
- 下一阶段针对上述 RVA 候选做函数边界、寄存器数据流、原始加载对象身份/调用图回溯；若缺乏确切来源，保持 `species_id_verified=0`、`material_enum_confirmed=false`。

## 检查点

| 核验项 | 已知情况 | 升级证据 |
| --- | --- | --- |
| 道具原生名称 | 9 语言 × 4,600 槽一致 | 已验证 |
| 道具原生图标 | 1,619 来源，1,615 ID | PNG + 哈希 + 参考比较已验证；不是每个物品都有图标 |
| 宝可梦纹理 PNG | 609 | PNG 原生来源/Hash 已验证，物种 ID 未验证 |
| 原生物种 ID 绑定 | 0 | 待真实原生表/消费者调用链 |
| 原生材料类型 | 未确认 | `00983.bin+0x26` 优先追踪，待原生枚举/调用链 |
| UI、素材等原生纹理 | 3,930 可关联，25 已抽样 | 按批次完整输出与人工抽查 |

所有结论以 GitHub Actions 实际执行报告为准；文档及脚本都不能自动把“候选”升级为“已确认”。
