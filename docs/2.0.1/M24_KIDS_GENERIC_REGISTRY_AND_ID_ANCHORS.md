# M24 / M24.1 — KIDS 类型注册函数与村民身份字段分离追踪

> Pokopia 2.0.1 · `2.0.1_unpack` · 原生 ExeFS `main` SHA256 `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`。
>
> 本轮都是**静态指令/数据字节证据**，并未连接实际游戏会话进行动态 GDB 读取，因此正式原生村民/物种 ID 对应数量维持 **0**。

关联：[[M23_FDATA_PLATFORM_AND_KIDS_CONSUMER]] · [[M22_VILLAGER_NATIVE_SOURCE_AUDIT]] · [[M20_NATIVE_SPECIES_ITEM_CALLGRAPH]]。

## 1. 结论：不要将通用注册器当作村民图标专属消费者

M23.1 在 `main+0xBB85CC` 证实了从 `main+0x34963B8` 指针装配 `main+0x32F0EE0` 方法表并写入 `main+0x366E6F0` BSS 对象的代码路径。M24 继续对原生 2.0.1 NSO 全量扫描，追踪 `main+0x1FDC1E0` 的直接调用者：

| 原始指令形式 | 唯一调用点数 | 证据 |
| --- | ---: | --- |
| `BL main+0x1FDC1E0` | **30** | 原始 ARM64 立即数分支 |
| `B main+0x1FDC1E0` | **3,916** | 原始 ARM64 立即数尾部分支 |
| 总计 | **3,946** | 无重复 PC |

这么多独立原生调用点提示它更像跨类型复用的注册/调度辅助函数，而非村民头像专属读取函数。**这只是一条有证据支持的功能方向判断；尚未证明该函数具体业务语义。**

M24 的另一项结果：从注册方法表起点 `main+0x32F0EE0` 起扫描，**连续 16 个 8 字节地址**的值都落在原始 ExeFS 可执行区（不是凭假设生成）。但这只是连续代码指针证据，**不能证明这 16 项全部属于同一个类的方法表**，也可能包含相邻类型布局。部分可复核的代码指针：

| 方法表偏移 | 原生 ExeFS 方法地址 |
| --- | --- |
| `+0x00` | `main+0xCE851C` |
| `+0x08` | `main+0xCE8520` |
| `+0x10` | `main+0x1FE4FA0` |
| `+0x18` | `main+0xCE854C` |
| `+0x20` | `main+0xCE861C` |
| `+0x30` | `main+0xCE8634` |

`main+0xCE854C` 已确定索引三个原始属性 Hash：`0xC8BB66DA` (G1T)、`0x2276FC56` (TEXINFO)、`0x2856A1B3`（source→target 对象引用）。但是，**它按调用者提供的索引输出一个属性描述结构，不是已证明的游戏物种 ID 属性消费者**。

M24 的“紧邻 ADRP+访存全局地址”严格匹配数是 0，这不否认 M23 的 `main+0xBB85B4/B8`：原始代码在 ADRP x1 与对应 LDR 之间插入了另一条 ADRP x8，本轮故意不将跨指令的寄存器保持假定为“紧邻调用”。M23.1 的特定上下文与原始指令字节校验依旧有效。

原始报告：[M24 调用统计和 16 方法表](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M24/m24_direct_calls_and_asm.json) · [M24 总账](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M24/m24_original_consumer_summary.json)。

## 2. M24.1 从 Pokémon 身份侧重新找入口

为了避免一直跟通用 KIDS 类构造器，额外检查原始 ExeFS 中存在且真实在指令中被引用的字符串（从此前 M11 原始来源清单交叉校验原始 rodata 字节和 ADRP+ADD 指令）：

| 原生标识 | 真实 ExeFS 引用点 main+ | 字节级结论 |
| --- | --- | --- |
| `RegisterPokemonNum` | `0x1135B44` | 字符串存在，原始可执行引用存在 |
| `pokemon_dex_id` | `0x1136AA4` | 原生字段名的字符串引用存在 |
| `pokemon_dex` | `0x11367D8` | 原生字符串引用存在 |
| `m_mainPokemonList` | `0x5FD168` | 原生字符串引用存在 |
| `m_pokemonDexHistory` | `0x5CC170` | 原生字符串引用存在 |
| `m_pokemonDexReadHistory` | `0x5CC1C4` | 原生字符串引用存在 |
| `m_pokemonHistory` | `0x5CC08C` | 原生字符串引用存在 |

**注意：原生文字 `pokemon_dex_id` 不等于 KIDS 原生属性 Hash `0x2856A1B3`，不能仅凭相同概念来匹配。**

找到一些可继续观察的调用关系：

- `main+0x1136AA4` 周边将字段名指针交给 `main+0x27470E0`（例如 `main+0x1136AB0`），周边还有 `main+0x2747070`。需要进一步确认这是反序列化元数据、注册表还是实际 runtime ID 读取。
- `RegisterPokemonNum` 在 `main+0x1135B44` 也经 `main+0x1135B4C` 进入 `main+0x27470E0`；表明它与上述入口共享同一辅助调用，但不证明两者之间的数据字段绑定。
- `m_mainPokemonList` 在 `main+0x5FD168` 送入 `main+0x5A71E0`；周边读 `[x19,#0x26]` 等状态字节，但 **x19 的身份未证明属于已知物品/宝可梦数据库结构**，不能与其他 +0x26 偏移相混淆。

图中所有原始反汇编和分支目标已保存：
- [M24.1 七个身份字段的原始汇编窗口](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M24/m24_1_identity_anchors_asm.json)
- [M24.1 身份锚点总报告](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M24/m24_1_identity_anchors_summary.json)

## 3. 剩余 79 + 9 的正式状态

| 任务 | 目前状态 |
| --- | --- |
| 79 张未定位原生村民头像 | **0 张新增**。M23 已确认两份 FF03 缺失容器的 521 条 G1T 尚未取得；不能声称其中有头像 |
| 9 张多候选头像 | **54 条类型字段到资源对象的字节证据保留**；游戏 ID → KIDS source OID 仍未证明 |
| 原生 KIDS 类型方法安装 | M23.1 静态字节已验证；M24 确认 16 个方法指针 |
| Pokémon ID 字段消费者 | M24.1 有 7 个原生字符串锚点，尚未与 KIDS 对象链闭合 |

任何 PokoHex 编号或原生图的文件名数字都不能直接回填 `native_species_id_verified`。

## 4. 复现

```bash
python -m pip install "lz4>=4,<5" "capstone>=5,<6"
python -m Scripts.resources.m24_kids_consumer_callgraph
python -m Scripts.resources.m24_1_pokemon_identity_anchors
```

[GitHub Actions：M24 Native KIDS consumer](https://github.com/969981/poko_resources/actions/workflows/unpack-m24-kids-consumer.yml)

## 5. 下一步更短路径

优先围绕 `main+0x1136AA4` 的原始字段描述生成函数，区分 ID 字段的实际读取/反序列化函数及最终载体；然后针对 `main+0x5FD168` 的 Pokémon 列表引用寻读回来的记录字段，在同一次调用中追踪是否出现一个可校验的 KIDS source OID。

如上述只是通用元数据注册，转向游戏运行时 **只读**断点记录：真实 game ID、KIDS source OID、0x2856A1B3 指向的 target OID、G1T Hash 必须在同一条执行轨迹中连成链，才能提升到正式映射。

原始 FDATA 搜索仍应并行沿 [[M23_FDATA_PLATFORM_AND_KIDS_CONSUMER]] 完成，但当前仓库不存在两个 FF03 实体，且未证明平台语义，不能虚构解包成果。
