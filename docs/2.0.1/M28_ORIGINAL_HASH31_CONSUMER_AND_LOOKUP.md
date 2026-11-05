# M28 — 原始 ExeFS 的 31 多项式搜索、KIDS 源对象检索和只读运行时取证

> Pokopia **2.0.1** · 分支 \`2.0.1_unpack\` · 原始 NSO0 \`2.0.1/exefs/main\` SHA-256：
>
> \`8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f\`
>
> M27 的 31 多项式是**原始 KIDS 字节的精确数学模型**，而不是当前已证明的原生函数。本轮没有新确定任何运行时 Pokémon species/villager ID；**307 高置信视觉候选、9 多候选、62 未定位**不变。

关联：[[M27_ORIGINAL_KIDS_REVERSE31_NUMERIC_HASH]] · [[M26_VILLAGER_ROSTER_AND_KIDS_PARALLEL_ARRAYS]] · [[M25_NATIVE_POKEMON_ICON_REGISTRY]]。

## 1. M28 原始 NSO 机器码扫描：31 倍乘积候选

对原始 NSO0 的全部 \`text\`（**41,194,624 B / 10,298,656 条 4 字节指令槽位**）直接解析 ARM64 操作码，并只解码有限候选的完整反汇编：

| 原始操作码或上下文 | 计数 | 证据含义 |
| --- | ---: | --- |
| 32-bit ADD/SUB 中 \`LSL #5\` | **319** | 仅有位移和加减 |
| 其中 ADD | **309** | 不能等同 \`33×oldHash\`；多数操作数来源不同 |
| 其中 SUB | **10** | 同样不能直接当作 \`-31×oldHash\` |
| 候选前后附近有 LDRB | **119** | 临近有字节读取，不代表操作数必然是同一字符串 |
| 临近有向后直接跳转 | **114** | 可能为循环，但尚未确认字符迭代 |
| MADD/MUL 前 14 条指令有同寄存器 MOVZ #31 | **0** | 仅排除这个受限的加载常量形式 |

**严格的 M28.1 两条 SUB 递推模板**：

\`\`\`asm
sub wTemp, wHash, wHash, lsl #5   ; -31 * wHash (mod 2^32)
sub wOut,  wChar, wTemp           ; wChar + 31 * wHash
\`\`\`

在这份原始 NSO、限定 32 位 SUB 同源寄存器和紧邻 LDRB 的检查范围内，没有命中这种连续局部模式（**0**）。

**M28.2 的另一种编译器模式**：

\`\`\`asm
add wTemp, wHash, wHash, lsl #5   ; +33 * wHash
sub wOut,  wTemp, wHash, lsl #1  ; +31 * wHash
\`\`\`

在 309 处 ADD shift-5 指令中，**没有一处将相同寄存器同时作为两个加法源操作数**，因此本模式第二跳和完整 \`+字节\` 均无匹配（**0**）。

这不是“游戏没有 31 进制 Hash 算法”的证明：编译器还可使用其它乘法、SIMD、内联函数、静态预生成表、索引预处理，也可能 Hash 在资源制作工具中而非运行时产生。继续做宽泛 opcode 扫描的收益有限，应优先追实际数据结构消费者。

源字节和限制范围：

- [M28 10,298,656 条原始代码扫描汇总](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M28/m28_31_instruction_search_summary.json)
- [M28.1 原生两 SUB 31 倍局部匹配结果](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M28/m28_1_local_31_recurrence_summary.json)
- [M28.2 ADD 33 倍减去两倍的原生指令分析](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M28/m28_2_33minus2_source_summary.json)
- [M28.2 同源 32 位 shift-5 ADD 原始指令清单](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M28/m28_2_native_shift5_same_source_survey.csv)

> M28 的大型候选汇编 JSON 包括筛选及本地取证参考，但它们不具有“完整函数实现已确认”的证据等级。

## 2. M28.3：已做成可直接使用的原生资源检索命令

脚本：\`Scripts/resources/m28_3_kids_icon_lookup.py\`。

查询 **TEXINFO 原始名称**而不是第三方 PokoHex 编号：

\`\`\`powershell
python -m Scripts.resources.m28_3_kids_icon_lookup --self-test
python -m Scripts.resources.m28_3_kids_icon_lookup --verify-all

# 已逐字节核验的例子：常规图标 0043
python -m Scripts.resources.m28_3_kids_icon_lookup --name icon_poke_0043_00_00_00

# 查真实原生数组槽位，即使尚未取得名称
python -m Scripts.resources.m28_3_kids_icon_lookup --slot 455

# 特殊形态或 uni 使用精确的原始 TEXINFO 名称
python -m Scripts.resources.m28_3_kids_icon_lookup --name icon_poke_uni_0025_00_00_00_nh
\`\`\`

**原生图标 \`0043\` 的可重复核验链**：

| 层 | 原始来源 | 值 |
| --- | --- | --- |
| TEXINFO 原名 | \`icon_poke_0043_00_00_00\` | 四位数字 \`0043\` |
| 倒序字符串 | \`3400\` | \`Hash31=0x0017F821\` |
| 第一原始数组 key | \`0xE88C8D60\` | **\`0x469E2C00\`** |
| 原生槽位 | 原始类型 \`0x9D1AFA46\` | **455** |
| 第二原始数组 Source OID | \`0x34CBB458\` | **\`0x06AB845F\`** |
| Source → Texture | 原始 \`0x2856A1B3\` | **\`0xC1A6D60C\`** |
| G1T Hash | 原始 Texture OID | **\`0xAB6768BD\`** |
| TEXINFO Hash | 原始 Texture OID | **\`0x2198D172\`** |

脚本读取原始 \`root_019167_50ae86ef.kidsobjdb\`，校验 SHA-256、3,543 个原始键/值，与 M25 的 629 Source OID 索引和 M27 14 组模型交叉检查。CI 中 \`--verify-all\` **626/626 全通过**，\`0043\` 的原生键、Source OID、Texture OID 均与原始二进制一致。

对于多个纹理别名共享同名的情况，输出 \`alternative_native_texture_name_alias_sources\` 并保留全部来源，不擅自按名称合并；不支持的形态、原生键不存在、Hash 键存在但值不一致均单独报告，不伪造结果。非数字 \`icon_poke_blank\`、\`icon_poke_uni_hatena\` 可按真实数组槽位查询，不套用四位数字模型。

[可用的完整查询脚本](https://github.com/969981/poko_resources/blob/2.0.1_unpack/Scripts/resources/m28_3_kids_icon_lookup.py)

[M28.3 已在原生数据库中验证的 0043 查询结果](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M28/m28_3_native_0043_name_to_source.json)

## 3. 运行时继续追踪：只读 GDB 取证工具

源文件 \`Scripts/gdb/m28_pokopia_native_id_readonly_trace.py\`，附独立 Python 语法检查 Actions。**没有接入用户实际模拟器，没有声称已完成动态断点验收**。

GDB 必须已经连接到**Pokopia 2.0.1 对应的 AArch64 进程**，并通过实际内存映射确认加载的原始主模块地址。不能用文件偏移或其它游戏 Build 的地址。示例：

\`\`\`gdb
source Scripts/gdb/m28_pokopia_native_id_readonly_trace.py
pokopia-m28-start 0xYOUR_ACTUAL_MAIN_LOAD_BASE 150 m28_runtime_trace.jsonl
continue
pokopia-m28-status
pokopia-m28-stop
\`\`\`

这里 \`0xYOUR_ACTUAL_MAIN_LOAD_BASE\` **必须替换为实际的十六进制加载基址**。运行的四个只读自动继续断点：

| 绝对地址计算 | 静态已知作用 | 采集目的 |
| --- | --- | --- |
| \`main_base + 0xDD1B48\` | KIDS 三属性描述器读取函数 | 观察 w3 属性索引、x30 返回地址 |
| \`main_base + 0xDD1C30\` | 类型 \`0x9D1AFA46\` 的 Type Hash getter | 观察真正调用者 |
| \`main_base + 0x1136AA4\` | \`pokemon_dex_id\` 字符串引用点 | 观察用户态调用上下文，字段语义待核验 |
| \`main_base + 0x5FD168\` | \`m_mainPokemonList\` 字符串引用点 | 观察列表上下文，记录结构待核验 |

输出为带时间、原始相对偏移、绝对 PC、调用者 LR、x0/x1/x2/x3 等寄存器的 JSONL，不写游戏内存、自动继续、达到限制后停用采集。**断点仍可能造成暂停开销，适合限定命中数量的小范围实验**。

此工具目前只能回答实际原生代码何时命中、谁调用它。真正的 ID 来源需要继续回读结构、跟踪对象分配/属性查询，而非把 \`w3\` 描述器索引误认成物种 ID。

## 4. M28 的准确研究结论

- **原生资源键 → 原生 Source OID → Texture OID → 原始 G1T/TEXINFO/PNG**：可用于 626 项数值图标名称，M28.3 已制作可重复运行的查询工具并与原始字节对账。
- **原生代码有没有直接的 \`31*hash + byte\` 实现**：截至 M28.2 的三种严格 AArch64 模式，没有证明；不能反推“必然在其它特定函数”。
- **游戏真实 species/villager ID → 资源名称或 3,543 项数组槽位**：尚未闭合。运行时证据可通过用户实际调试环境再获取；目前正式绑定仍然为 0。
- **307 / 9 / 62 村民头像**：没有新增已确认图像，也没有把 PokoHex 的角色 ID 按名称写成官方原生 ID。

## 5. 所有 CI

- [M28 全 1,030 万原生指令槽位扫描](https://github.com/969981/poko_resources/actions/runs/42006957167)
- [M28.1 双 SUB 31 递推分析](https://github.com/969981/poko_resources/actions/runs/42007361234)
- [M28.2 33 倍减两倍表达式](https://github.com/969981/poko_resources/actions/runs/42007728970)
- [GDB 只读脚本的静态语法与无内存写入检查](https://github.com/969981/poko_resources/actions/runs/42008096666)
- [M28.3 626 项精确名称→Source OID 查询](https://github.com/969981/poko_resources/actions/runs/42008387363)

这些 Actions 全部成功，**GDB 项仅是静态语法和源代码检查，未代表实际模拟器断点测试**。

## 6. 下一最短研究路径

1. **真正的双数组消费者**：从 \`main+0xDD1B48\` 和 \`0xDD1C30\` 的实际调用者开始，定位原生对象载体、谁读取 \`0xE88C8D60\` 的键，以及何时取出 \`0x34CBB458\` 的 Source OID。静态哈希候选不值得无限扩大。
2. **同一运行时实体双向核查**：只有在同一次角色/头像加载中同时取得实际 game ID、所选数组键/槽位、Source OID 以及 M25 的纹理 OID，才把某条关系升级为正式 ID 绑定。
3. **未定位的 62 张**：应维持原始图像索引限定的负结果，与 M23 缺失的 FF03 容器及 PokoHex 版本来源分开记录，不能根据连续参考 ID 宣布属于哪个 DLC。
