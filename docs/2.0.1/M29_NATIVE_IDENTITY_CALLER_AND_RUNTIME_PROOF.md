# M29 — 原生身份字段三路径复核、KIDS 类初始化边界与运行时取证闭环

> **Pokopia 2.0.1 / \`2.0.1_unpack\`**。原始执行文件 \`2.0.1/exefs/main\` SHA256 \`8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f\`。  
> **当前 307 张高置信原生视觉候选 / 9 张多候选 / 62 张未定位，原生游戏身份绑定为 0。** 本阶段追踪了原生三个文本入口及其通用处理器，但没有伪造任何游戏物种 ID 与纹理索引。

关联：[[M28_ORIGINAL_HASH31_CONSUMER_AND_LOOKUP]]、[[M27_ORIGINAL_KIDS_REVERSE31_NUMERIC_HASH]]、[[M26_VILLAGER_ROSTER_AND_KIDS_PARALLEL_ARRAYS]]、[[M25_NATIVE_POKEMON_ICON_REGISTRY]]。

## 1. 原始代码证据：这三个文本入口不等于头像选择函数

以固定 SHA 原始 \`NSO0\` 段的 ARM64 指令、rodata 字符串原字节与原始直接 \`BL\` 目标同时核验：

| 原始指令入口 | 字面量 | 可证明的局部行为 | 原生直接 helper |
| --- | --- | --- | --- |
| \`main+0x1135B44\` | \`RegisterPokemonNum\` | 调用前有 \`w21\` 的最大 1000 次范围控制，读取/更新计数，\`x2\` 接收扩展后的 \`w8\`；这是计数/日志**候选**，不是物种映射证明 | \`main+0x27470E0\` |
| \`main+0x1136AA4\` | \`pokemon_dex_id\` | 读取 \`[x22+4]\`、\`[x22+6]\`、\`[x22+8]\` 的 u16，执行 \`value-1 <= 0x1F3\` 范围约束和记录位图读取；\`x21\` 通过 \`x2\` 传给写入/转换 helper | \`main+0x27470E0\` |
| \`main+0x5FD168\` | \`m_mainPokemonList\` | 对 \`[x19+0x26]\` 字节标志做多次 \`tbz/tbnz\`；字符串地址传 \`x3\`、\`x19/x21\` 传 \`x1/x2\` | \`main+0x5A71E0\` |

具体源字节片段：

\`\`\`asm
main+0x1136A60 ldrh w8,[x22,#8]      ; 原始 u16 候选
main+0x1136A64 sub w9,w8,#1
main+0x1136A68 cmp w9,#0x1f3
main+0x1136AAC mov x2,x21
main+0x1136AB0 bl #0x27470e0

main+0x5FD164 adrp x3,#0x27d2000
main+0x5FD168 add x3,x3,#0xb35       ; m_mainPokemonList
main+0x5FD16C mov x1,x19
main+0x5FD170 mov x2,x21
main+0x5FD174 bl #0x5a71e0

main+0x1135B14 cmp w21,#0x3e8
main+0x1135B3C sxtw x2,w8
main+0x1135B4C bl #0x27470e0
\`\`\`

**注意**：\`pokemon_dex_id\` 的文本名很像 ID，但附近 u16 的存储布局、位图行为还不能证明 \`x22+8\` 是物种 ID，更无法从中直接推断头像编号。\`RegisterPokemonNum\` 的计数值更不能根据标签名当作资源编号。

## 2. 明确的负连接：类元数据、三个入口来自不同的代码区域

原生类型 \`0x9D1AFA46\` 对应的 KIDS 方法：

- \`main+0xDD1B48\`：三项属性描述器枚举，包括数组 \`0xE88C8D60\`、\`0x34CBB458\`。
- \`main+0xDD1C30\`：类型 Hash getter，已由原始 vtable +0x28 定位。
- \`main+0x349C2E0\`：初始化的 BSS 类实例指针。
- \`main+0x349C2E8\`：初始化的方法表指针。

本轮扫描原始代码得到：**7 条类初始化全局地址候选引用（其中 3 条相邻 ADRP→LDR）**，全部位于 \`main+0xBE19B4\` 到 \`main+0xBE1A58\` 的类型注册代码区域；不是已证明的角色 UI 数据读取消费者。

直接 \`BL/B\` 到属性描述器方法 \`0xDD1B48\` 和类型 getter \`0xDD1C30\` 都为 **0**，但二者在 C++/KIDS 运行时通过方法表的间接 \`BLR\` 调用是可能的：**不能因此断言无人调用**。

对三个 ID/列表入口的 helper 做原始全代码目标汇总：

| helper | 直接 BL 总数 | 说明 |
| --- | ---: | --- |
| \`main+0x27470E0\` | **110** | \`pokemon_dex_id\` 和 \`RegisterPokemonNum\` 共享；有多处相似输出语境 |
| \`main+0x5A71E0\` | **1,109** | 广泛复用，不是可据以认定的特定头像查询 |
| \`main+0x113AF80\` | **1,479** | 大量编码/记录类型路径使用 |
| \`main+0xDD1B48\` | **0** | 属性枚举为方法表成员；直接 BL 无法覆盖间接调用 |
| \`main+0xDD1C30\` | **0** | 同上 |

以上均为原始 AArch64 **直接调用计数**，不是调用次数或执行热度统计。

[原生 M29 三入口、全局引用、helper BL 明细](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M29/m29_original_identity_anchor_context_and_KIDS_class_refs.json)  
[M29 汇总 JSON](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M29/m29_native_identity_consumer_triage_summary.json)

## 3. 更有针对性的下一阶段：只读 GDB 硬件断点采样

更新后的调试工具 \`Scripts/gdb/m28_pokopia_native_id_readonly_trace.py\`：

- 硬件断点优先且**不静默回退软件断点**，以免不知情地在目标原生指令上做 \`int3/brk\` 软件补丁。模拟器 GDB Stub **必须支持硬件断点**；若不支持会报错，不能宣称已验收。
- 除 \`x0–x4\`、\`x8–x10\`、\`x30\` 外，追加 \`x19–x26\`、\`x28\`，便于分析 \`x22\` 的记录/ID 候选及 \`x19/x21\` 列表消费者。
- 同一原始版本下观察 \`main+0xDD1B48\`、\`0xDD1C30\`、\`0x1136AA4\`、\`0x5FD168\`，收集真实的 PC、LR、x 寄存器和描述器索引，自动继续、指定最大命中次数。
- **未连接实际模拟器；当前仅通过代码静态语法检查，不能声称硬件断点已被目标支持或任何身份已绑定。**

步骤（\`0xYOUR_MAIN_BASE\` 必须用目标实际加载的 \`main\` 地址替换）：

\`\`\`gdb
source Scripts/gdb/m28_pokopia_native_id_readonly_trace.py
pokopia-m28-start 0xYOUR_MAIN_BASE 150 m28_runtime_trace.jsonl
continue
pokopia-m28-status
pokopia-m28-stop
\`\`\`

## 4. 新增 M29.1 运行时 JSONL 来源检查

\`Scripts/resources/m29_1_validate_gdb_trace.py\` 在独立 CI 中可复现自测：

\`\`\`powershell
python -m Scripts.resources.m29_1_validate_gdb_trace --self-test
python -m Scripts.resources.m29_1_validate_gdb_trace --input m28_runtime_trace.jsonl --out m29_runtime_validation
\`\`\`

提供实际 GDB JSONL 后，会严格检查：

- 固定 2.0.1 原始 \`main\` SHA 的声明值、真实事件 PC=\`main_base + 原始相对偏移\`；
- 只接受四个已建模代码入口、合法的 16 进制寄存器、合规事件数量、原始属性描述器索引；
- 防止 JSONL 内把任何未验证字段直接标为 \`game_species_id_verified\`、\`kids_source_oid_verified\` 或 \`runtime_same_instance_link_verified\`；
- 输出每个原生入口的 LR 频数和 \`0/1/2\` 描述器候选分布，便于进一步针对真实调用者做反汇编，而不是盲扫。

**重要证据局限**：该程序不能证明用户提交的文本确实来自实机、模拟器或完全正确的运行版本。即使同一 JSONL 中同时命中身份字符串和 KIDS 方法，也只是同一会话，并不等于**同一个角色对象**的调用链，绝不据此填正式映射。

CI 只提供模拟 JSONL 的合法/非法案例，不提供真正 GDB 运行数据。

## 5. 何时才能真正将身份关系升级？

原生图标资源的后半段已经完全建立：

\`\`\`text
原生 KIDS 数组 key
    → 原生 KIDS Source OID
    → 属性 0x2856A1B3
    → Texture OID
    → G1T / TEXINFO Hash
    → 原生 PNG
\`\`\`

仍缺前半段：

\`\`\`text
游戏运行时同一个 Pokémon/villager 实例
    → 实际物种 ID / 形态字段来源（读指令 + 数据结构）
    → 原生 key 生成/查询位置
    → KIDS Source OID
\`\`\`

从字符串、位图或 PokoHex 参考 ID 猜出来的数字，不能进入这一正式证据链。

**当前 307/9/62 保持不变。** 对 9 张多候选保留 M26 的互斥最优视觉方案；对 62 张缺失头像保留 M26.1 的 629 Source OID 范围内负结果，不因连续参考 ID 就宣称属于任何新版本、隐藏资源或 DLC。

## 6. 可复现 CI

- [M29 原生三入口和 KIDS 类关联](https://github.com/969981/poko_resources/actions/runs/42009731562)
- [M28 硬件断点版本语法和无主动游戏数据修改检查](https://github.com/969981/poko_resources/actions/runs/42010018483)
- [M29.1 JSONL 原始 PC 与不实身份绑定拒绝](https://github.com/969981/poko_resources/actions/workflows/unpack-m29-1-gdb-trace-validator.yml)
