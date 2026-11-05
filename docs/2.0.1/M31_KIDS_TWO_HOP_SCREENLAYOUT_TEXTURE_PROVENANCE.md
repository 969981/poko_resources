# M31 — ScreenLayout 方法表、两跳包装资源链和 628 条原生图标溯源

> Pokémon Pokopia **2.0.1** · 分支 \`2.0.1_unpack\`  
> ExeFS \`2.0.1/exefs/main\` SHA-256：\`8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f\`  
> 原始 \`root_019167_50ae86ef.kidsobjdb\` SHA-256：\`86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541\`
>
> 研究边界：**628 条 Source→包装 IDOK→G1T/TEXINFO 原始两跳字节关联已闭合**；**游戏 species/form/villager ID 如何选择这个 Source OID，仍未得到原生调用链**。头像统计 **307 高置信视觉候选 / 9 多候选 / 62 未定位**，正式运行时 ID 绑定仍是 **0**。

关联：[[M30_SCREENLAYOUT_NATIVE_CLASS_AND_WITNESS]] · [[M29_NATIVE_IDENTITY_CALLER_AND_RUNTIME_PROOF]] · [[M28_ORIGINAL_HASH31_CONSUMER_AND_LOOKUP]] · [[M27_ORIGINAL_KIDS_REVERSE31_NUMERIC_HASH]] · [[M26_VILLAGER_ROSTER_AND_KIDS_PARALLEL_ARRAYS]] · [[M25_NATIVE_POKEMON_ICON_REGISTRY]]。

## 1. M31/M31.1：静态方法表，补全了原生 BLR 属性遍历路径

两个已经在 M30.5 从原始字符串注册中还原正式名称的类：

| 原始类名 | Type Hash | 方法表 | \`vtable+0x18\` 属性方法 |
| --- | --- | --- | --- |
| \`ScreenLayoutTexturePackSettings\` | \`0x9D1AFA46\` | \`main+0x33135C8\` | \`main+0xDD1B48\` |
| \`StaticScreenLayoutTextures\` | \`0x79991E79\` | \`main+0x32F0EE0\` | \`main+0xCE854C\` |

M31 对两个方法表的**连续 16 个 u64 单元（每表 0x80 字节）**进行原始二进制校验：共 32 个值均指向原始 \`text\`，对应 23 个不同代码目标。**本次仅检验这 16 格，不代表证明了完整 C++ vtable 边界。** 通过原始目标 RVA 的直接 \`BL/B\` 搜索，此范围内入口均无直接调用者；这不覆盖虚函数间接调用。

真正的新证据是两类的 **\`vtable+0x10\` 都指向同一个原始代码 \`main+0x1FE4FA0\`**。源码字节级复核：

\`\`\`asm
main+0x1FE4FBC  mov x21,x0
main+0x1FE4FC4  ldr x8,[x21]
main+0x1FE4FCC  mov x1,x19
main+0x1FE4FD0  mov w2,#1
main+0x1FE4FD4  mov w3,w22
main+0x1FE4FD8  ldr x8,[x8,#0x18]
main+0x1FE4FDC  blr x8
main+0x1FE4FE0  ldr w8,[x19,#4]
main+0x1FE4FE8  add w22,w22,#1
main+0x1FE4FF0  b.ne #0x1fe4fc4
\`\`\`

该结构用 \`w22\` 的索引循环枚举**属性描述器**，通过类型方法表分发 \`vtable+0x18\`。源码 \`main+0xDD1B48\` / \`main+0xCE854C\` 的完整局部指令进一步确认，主要按索引读取类静态属性 Hash 和字段标签，构造输出描述符；**它们不是已证明的 3,543 项数据搜索器，也不是物种 ID → 头像选择函数**。

共同遍历器 \`0x1FE4FA0\` 在原始初始化 data 中出现 **1,990 个指针引用**，是跨大量类型的公共机制，不能因为它链接到两种 ScreenLayout 类，就把所有调用者都视为图标消费者。

[方法表 32 单元源字节分析](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M31/m31_original_screen_layout_method_table_bounded_scan.json) · [公共 BLR 分发与两种完整属性方法原生反汇编](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M31/m31_1_common_native_KIDS_enumerator_and_property_asm.json)。

## 2. M31.2：恢复 \`StaticScreenLayoutTextures\` 三项正式属性名

原始 \`main+0xCE854C\` 中的属性描述器从 \`main+0x2830C90\` 读取三个 Hash，并从 data \`main+0x3330928\` 读取三个原始 UTF-8 字符串指针：

| Hash | 原始字段名 | 原始字符串地址 |
| --- | --- | --- |
| \`0xC8BB66DA\` | \`LayoutTexturesRenderStateObjectHash\` | \`main+0x279FF20\` |
| \`0x2276FC56\` | \`LayoutTexturesInfoDataResourceHash\` | \`main+0x27FAA50\` |
| \`0x2856A1B3\` | \`WrapStaticScreenLayoutTexturesObjectHash\` | \`main+0x27C6DDD\` |

这是来自游戏原始 ExeFS 的**字段真实名称**，不是研究者推测的中文含义。

必须纠正旧命名：M16 曾把 \`0x2856A1B3\` 称作 \`third_unknown\`；M25–M30 的 \`target_texture_oid\` 列实际保存的是此字段的数值，即 **\`WrapStaticScreenLayoutTexturesObjectHash\`**。该值指向一个**真实包装 IDOK 对象**，不是已证实的最终 G1T/TEXINFO 文件哈希。

[三字段源码、原始指针及样本字节](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M31/m31_2_original_StaticScreenLayoutTextures_3_field_labels.json)。

## 3. M31.3/M31.4：找到了所有 628 个包装 IDOK 对象

对原始数据库全部 7,087 个 IDOK 节点直接解析后，M25 **628 个**主索引图标 Source OID 都是一种 \`0x79991E79\` 类型的 \`StaticScreenLayoutTextures\` 对象，其原始三个字段：

| 父对象字段 | 全部 628 个对象原始值 |
| --- | --- |
| \`LayoutTexturesRenderStateObjectHash\` | \`0x00000000\` |
| \`LayoutTexturesInfoDataResourceHash\` | \`0x00000000\` |
| \`WrapStaticScreenLayoutTexturesObjectHash\` | 628 个不同的包装对象 OID |

其中 **628/628 个包装 OID 均真实存在于同一原始 KIDSOBJDB 的 IDOK 节点表**，而且这 628 个子对象也都是 \`0x79991E79\` 类型、同样只有三个 \`kind=5,count=1\` 的字段。

这一步曾暴露旧索引的歧义：M25 的 \`g1t_hash\` / \`texinfo_hash\` 不是**父对象**前两个字段的数值。父对象前两字段实际为 0。M31.3 在输出中将父对象原始 u32 与 M25 文件 Hash 单独保存，不再混同；M31.4 继续逐个走入第二层对象，才找到了它们的原始文件 Hash。

- [628 父对象按原始字段名的纠正清单](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M31/m31_3_corrected_628_native_texture_object_fields.csv)
- [628 个包装 IDOK 对象及 1884 个原生属性记录](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M31/m31_4_original_628_wrapper_IDOK_typed_field_graph.csv)

## 4. M31.5：原生资源两跳闭合，628 条全部精确核验

对 628 个父对象及各自 628 个子对象同时检查，真实 KIDS 字节、M25 G1T 文件 Hash、TEXINFO 文件 Hash 全部相等：

\`\`\`text
TexturePackObjectHashArray[index]   # 已验证的原始 3543-u32 数组
  │
  └── Source OID → 第一层 StaticScreenLayoutTextures，Type 0x79991E79
       ├── LayoutTexturesRenderStateObjectHash  = 0
       ├── LayoutTexturesInfoDataResourceHash   = 0
       └── WrapStaticScreenLayoutTexturesObjectHash
                 │
                 ▼
            第二层 StaticScreenLayoutTextures，Type 0x79991E79
              ├── LayoutTexturesRenderStateObjectHash = G1T 文件 Hash
              ├── LayoutTexturesInfoDataResourceHash  = TEXINFO 文件 Hash
              └── WrapStaticScreenLayoutTexturesObjectHash = 0
\`\`\`

所有 628 项分别检查源对象 OID、包装对象 OID、原始 IDOK 位置、属性偏移、字段 Kind/Count、包装层 3 个原始 u32、M25 已建立的 G1T/TEXINFO 资源名称和文件 Hash。**父对象两个原始 0 值、子对象末尾 0 值在 628/628 项中成立**。

示例：原始 \`icon_poke_0043_00_00_00\`（注意：\`0043\` 仍是纹理文件名四位数字，不是已认证游戏 ID）：

| 类型 | 原始值 |
| --- | --- |
| 3543 数组槽位 | \`455\` |
| TexturePack Key | \`0x469E2C00\` |
| 第一层 Source OID | \`0x06AB845F\` |
| 第二层包装对象 OID | \`0xC1A6D60C\` |
| 包装对象 RenderState 字段 / 对应 G1T Hash | \`0xAB6768BD\` |
| 包装对象 InfoData 字段 / 对应 TEXINFO Hash | \`0x2198D172\` |

**这条完整的资源字节关联已被原始文件证明**；仍没有证明游戏的某次实际角色选择流程执行了这些指针查找。

[**M31.5 规范化的 628 行完整两跳资源 CSV**](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M31/m31_5_canonical_628_two_hop_KIDS_asset_provenance.csv) · [原始字节校验摘要](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M31/m31_5_full_two_hop_source_asset_report.json)。

其中 M25 的 \`629\` 个总 Source OID 含一项不在 \`B4A1803B\` 主数组的独立来源，本轮 **628 行规范化表没有把那项遗漏误记成失败**；其单独来源需保留。

## 5. 已同步修复现有 M28.3 查询工具

\`Scripts/resources/m28_3_kids_icon_lookup.py\` 现在在查询任意图标时直接打开同一原始 KIDSOBJDB，检查父对象、包装对象以及两条文件 Hash：

\`\`\`powershell
python -m Scripts.resources.m28_3_kids_icon_lookup --verify-all
python -m Scripts.resources.m28_3_kids_icon_lookup --name icon_poke_0043_00_00_00
python -m Scripts.resources.m28_3_kids_icon_lookup --slot 455
\`\`\`

为兼容旧调用者，输出字段 \`texture_oid\` 暂时仍在，但**必须只按历史兼容字段使用**，新增以下正名：

- \`original_wrapper_IDOK_oid\`：原始包装对象 OID；
- \`original_wrapper_render_state_file_hash\`：来自第二层原始对象的 RenderState 值，可与 M25 G1T 文件 Hash 精确对账；
- \`original_wrapper_info_data_file_hash\`：来自第二层原始对象的 InfoData 值，可与 M25 TEXINFO 文件 Hash 精确对账；
- \`source_to_wrapper_to_G1T_TEXINFO_bytes_verified\`：两跳均经过原始二进制校验；
- \`final_texture_object_ID_proven_from_legacy_texture_oid=false\`：杜绝旧字段误导。

更正 \`texture_oid\` 含义不会改变已验证的原始数值、图像来源和 307/9/62 的视觉证据统计。

## 6. 仍未达到的游戏实际身份证明

M31 已证明：

\`\`\`text
3543-array index → Resource Source OID
  → 原生父 IDOK → 原生包装 IDOK → G1T/TEXINFO 文件 Hash
\`\`\`

还**没有**证明：

\`\`\`text
Pokopia 游戏中同一个村民/宝可梦对象
  → 物种 ID 与形态的原生读取
  → ScreenLayout 运行时选择 TexturePack Key
  → 查询 3543 项数组索引
\`\`\`

属性描述器遍历器 \`main+0x1FE4FA0\` 是通用序列化/元数据机制；它调用属性枚举方法，不等于运行时按 ID 查找纹理。下一阶段应抓 **真正的 ScreenLayout Key→Object 数据消费者**，或在有可靠运行中 GDB 时，从同一操作实例验证真正的物种/形态读取与 Source OID 命中。这两类都需要代码/字节证据，不能依赖名称相似。

**未连接实际运行中的游戏，正式游戏原生身份绑定仍为 0。**

## 7. 已成功 CI

- [M31 方法表 32 槽位源字节审计](https://github.com/969981/poko_resources/actions/runs/42016491354)
- [M31.1 原始通用间接 \`BLR\` 属性迭代](https://github.com/969981/poko_resources/actions/runs/42016827786)
- [M31.2 三项 \`StaticScreenLayoutTextures\` 字段原生名称](https://github.com/969981/poko_resources/actions/runs/42017091247)
- [M31.3 628 原始父对象字段语义复核](https://github.com/969981/poko_resources/actions/runs/42018092811)
- [M31.4 628 包装 IDOK 对象与 1884 字段](https://github.com/969981/poko_resources/actions/runs/42018246741)
- [M31.5 两跳 G1T/TEXINFO 628/628 完整校验](https://github.com/969981/poko_resources/actions/runs/42018526109)
- [M28.3 查询工具的包装层纠偏及 626 原生名称复验](https://github.com/969981/poko_resources/actions/runs/42018740727)

这些均是**原始文件、静态代码与离线来源索引验证**，不代表真实模拟器 GDB 断点或运行时物种 ID 绑定成功。
