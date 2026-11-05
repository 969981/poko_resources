# M9.3–M9.5 — KIDSOBJDB `_RNK0000` 名称资源与原版 ExeFS 属性 Hash 消费证据

分支：`2.0.1_unpack`。**状态：原生名称资源的预期身份已恢复，但对应 `_RNK0000` 二进制在仓库现有 M3/FDATA 资源范围内缺失。ExeFS 的 3 条 Hash→字符串元数据构造路径已取得指令级证据，仍不能推断剧情、任务、建筑的文本外键。**

## M9.3：头部自带配套名称表的 Hash

对 M9.2 已逐字节验证的三份原生 KIDSOBJDB，读取 `_DOK0000` 文件头 `u32@0x14`，不是在属性值中猜名称：

| 原始 KIDSOBJDB 资源 Hash | 原生名称资源 Hash | M3 派生索引（不等于原始 RDB） | 对应 IRNK 字符串 |
|---|---|---|---|
| `d14d76ef` | `aa91cb96` | 0 匹配 | 未取得 |
| `cfd2bd1f` | `a91711c6` | 0 匹配 | 未取得 |
| `b290631c` | `cb3c8b15` | 0 匹配 | 未取得 |

核对 89,507 条 M3 派生资源索引后，三组均为 `RNK_NAME_FILE_MISSING`。**M9.6 已补做原始 root/system RDB 逐条核对，确认三个 Hash 均有真实原始记录（见下文）；此前的 0 匹配只表示 M3 已解码覆盖不足，绝不表示原始 RDB 无记录。** 原始 FDATA 仍未纳入仓库，不得因此生成属性名称。

解析器 [`Scripts/resources/m9_rnk_name_tables.py`](https://github.com/969981/poko_resources/blob/2.0.1_unpack/Scripts/resources/m9_rnk_name_tables.py) 已实现标准结构：

- 顶层 `_RNK0000`、24 字节头部、条目计数和原始文件大小验证。
- 每个 `IRNK0000` 的原生长度、名称 Hash、字符串数、相对于条目起点的字符串偏移、UTF-8 与 4 字节对齐填充验证。
- 精确的配套资源 Hash 定位、Git 受控 Blob 读取、SHA-256、来源 M3 ID 和属性/对象 Hash 交集对照；同 Hash 多来源保留歧义，验证不通过拒绝升级。
- IRNK 键与对象 ID 匹配和与属性名 Hash 匹配是不同证据，不可把 IRNK 字符串序号直接当作“字段名称”。

来源代码：
[上游 `yumia_decode_kidsobjdb.py`](https://github.com/eArmada8/yumia_fdata_tools/blob/9d8dc1fb7436f14ffec42acb6d719cea1214abbd/ktid/yumia_decode_kidsobjdb.py)，同时以 M9.1/M9.2 的本游戏真实数据复核。

**M9.3 成功核验工作流**：[41951158981](https://github.com/969981/poko_resources/actions/runs/41951158981)。相关文件 `rnk_report.json`、`rnk_owner_sources.csv`、`rnk_resource_candidates.csv`、`rnk_property_hash_matches.csv`、`rnk_object_id_matches.csv`。

## M9.4：ExeFS ARM64 属性 Hash 地址引用

原版 `2.0.1/exefs/main` 的 SHA-256：
`8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`。

- 静态检查 29 种目标 Hash；25 组分节 / Hash 组合发现四字节对齐数值命中（不是 25 个已验证调用者）。
- 检查到 3 处 `MOVZ + MOVK` 完整 32 位 Hash 构造。
- 对 115 个候选 rodata 字节偏移恢复 9 个相邻 `ADRP + ADD` 地址构造点，**0 个直接 `ADRP + LDR` 属性值读取点**。因此 `ADD_ADDRESS` 只能称为常量地址引用，不能标注为读/写属性。
- 原始字节、指令地址、寄存器和候选数据地址在 `exefs_property_hash_consumers.json`、`exefs_property_hash_xrefs.csv/json` 中。

**M9.4 成功核验工作流**：[41951784826](https://github.com/969981/poko_resources/actions/runs/41951784826)。

## M9.5：已验证的元数据 Hash 与邻近字符串指针写入

进一步对实际 ARM64 反汇编检查 `MOVZ/MOVK → STP W*,W* → STP X*,X*` 关系。以下 3 个 Hash 被构造后通过 `STP` 存储；紧接着同一个内存基址下另一个 `STP` 写入包含原版 rodata 字符串地址的指针。**这证明它们在同一个元数据构造路径中被共同写入，不代表已经验证了该属性在运行时被 KIDSOBJDB 的 getter 读取。**

| 属性 Hash 常量 | 同路径关联的 ExeFS 原版字符串 | MOVZ 起始地址 | 证据 |
|---|---|---|---|
| `0x0b6e1578` | `DisplaysetObjectNameHash` | `main+0xCA2C80` | Hash 和字符串地址在同组描述符写入 |
| `0xe21ff09f` | `ObjectNameHashArray` | `main+0xD38530` | 同上 |
| `0xf92c5190` | `TexturesRenderStateObjectHash` | `main+0xD59460` | 同上 |

这三条是 **ExeFS 静态元数据中的 Hash→字符串标签候选**，不是缺失的 `_RNK0000` 原生名称表，也不是已经证明的 M7 文本外键。

- `exefs_hash_name_candidates.csv/json`：直接检索 Hash、字符串、ARM64 指令 PC、寄存器、rodata 地址、原版二进制 SHA 与证据等级。
- `exefs_descriptor_hash_writes.csv/json`：保留完整反汇编、两次 STP 的寄存器与共享内存基址、候选字符串指针。
- `evidence_grade=ARM64_DESCRIPTOR_HASH_AND_STRING_POINTER_PAIR`。
- `rnk_name_table_verified=false`、`semantic_property_name_verified=false`、`runtime_property_getter_verified=false`、`script_or_scene_text_foreign_key_verified=false`。

**M9.5 成功核验工作流**：[41952223555](https://github.com/969981/poko_resources/actions/runs/41952223555)。

## 对 87,445 条数值候选的影响

M9.2 的三份库中共有 101,467 个对象、1,176,984 条已验证类型的属性、87,445 条 `u32 == local OID` 候选。

- 现阶段只确认候选的数值与类型，**尚未证明其引用身份**。
- 获得 ExeFS 中一个 Hash 的字符串标签，不能凭此认定所有相同 Hash 属性值都是对象外键。
- **剧情、任务、建筑和系统 UI 对 M7 原生文本的新增正式外键：0。** 数据库中的相应类别仍必须保留 `UNKNOWN`。

## 后续剩余的最短证据路径

1. 利用 `aa91cb96`、`a91711c6`、`cb3c8b15` 精确核对未覆盖的 FDATA/原始 RDB 记录、其他合法的官方资源包；若能拿到真实 `_RNK0000` 数据，再由现有解析器验证 IRNK 字段。
2. 继续围绕上述 3 个 `STP` 写入地址恢复描述符初始化函数、注册表基址与实际读取这些描述符的调用者；这是验证 Hash→字段名→访问器的关键，不能仅检查字符串相近。
3. 寻找实际脚本／任务对象中的 `property_hash → (text table resource key, row id)` 消费函数，再与 M7 的 179+ 组候选/原始九语言记录对账。脚本引用缺失时不得设定 Quest/Dialogue/Building 分类。

原生文件不重写，所有派生 CSV/JSON 与校验日志存放在本目录的子目录中。


## M9.6：原始 root/system RDB 复核已突破 M3 索引缺失

[Actions #41953543449](https://github.com/969981/poko_resources/actions/runs/41953543449) **Success**。新增 `Scripts/resources/m9_rnk_original_rdb_audit.py`，用已验证的原始 RDB/RDX 解析器扫描 `root.rdb` 60,722 条、`system.rdb` 25,110 条记录，并检查三条 RDB 给出的 FDATA 来源文件是否在原始 Git 树出现。

| RNK Hash | 原生 root RDB 记录 | RDB entry 字节偏移 | 配套 FDATA（尚缺） | FDATA 字节偏移 | 存储 IDRK 字节数 | 预期解压字节数 |
|---|---|---:|---|---:|---:|---:|
| `a91711c6` | `root:40061` | 3,795,248 | `0xea42a223.fdata` | 4,011,152 | 105,313 | 796,572 |
| `aa91cb96` | `root:40411` | 3,828,344 | `0x5c83387f.fdata` | 22,728,928 | 5,934,913 | 29,946,788 |
| `cb3c8b15` | `root:48184` | 4,563,988 | `0x898afd6d.fdata` | 16 | 2,342,018 | 12,353,940 |

三条原始 RDB 的 `type_hash` 均为 `bf6b52c7`，`footer_magic=0x0401`。这都是 **RDB 索引真实记录**，但配套物理文件未出现在本分支原始 FDATA 路径及 MountPoint 目录中，仍未执行文件内 `IDRK → _RNK0000/IRNK0000` 字节验证。不能写成“RNK 已恢复”。

完整证据：`rnk_original_rdb_audit.json`、`rnk_original_rdb_matches.csv`。这次修正了“原始 RDB 没有名称 Hash”的潜在错误判断。

## M9.7：描述符填充函数的入口和静态指针槽

[Actions #41953892512](https://github.com/969981/poko_resources/actions/runs/41953892512) **Success**。ARM64 指令显示三处 Hash 写入属于按 `x2` 数量、`x3` 索引选择、向 `x1` 缓冲区写入 **24 字节结构体** 的描述符填充函数。具体调用约定仍需调用点验证。

| 属性 Hash | 入口候选 | 对应 `.data` 64 位入口地址指针槽 |
|---|---|---|
| `0x0b6e1578` | `main+0xCA2C40` | `main+0x32ECF60` |
| `0xe21ff09f` | `main+0xD384C0` | `main+0x32FA020` |
| `0xf92c5190` | `main+0xD59420` | `main+0x32FDFD8` |

扫描直接 `BL/B`、`ADRP+ADD`、`.data/rodata` 静态 64 位指针，共找到 **3 处真实静态指针字节匹配**，没有恢复直接调用点。下一轮应围绕这三个指针槽追踪指针表及其间接调用方，并继续追踪描述符填充后的读取端；不能把指针槽匹配当成 getter 或脚本外键。

完整证据：`exefs_descriptor_entry_xrefs.json/csv`；分析器 `Scripts/resources/m9_descriptor_reader_trace.py`。

## M9.8：补齐物理 FDATA 后的严格提取器

新增 `Scripts/resources/m9_rnk_from_original_fdata.py` 和单元测试、Actions 工作流。使用 M9.6 已证明的 RDB 来源、`fdata_offset`、`entry_size`、`name_hash`、`type_hash`、解压长度校验 `IDRK`，然后执行既有的 `parse_rnk` 严格解析，输出原始字节 SHA-256 和逐条 IRNK 来源。**这项工具不凭缺失资源编造字符串，当前执行是否成功以本轮 CI 结果和报告为准。**

在仓库根目录提供有权使用的原始物理 FDATA 后可运行：

```bash
PYTHONPATH=. python Scripts/resources/m9_rnk_from_original_fdata.py \
  --audit-csv UnPack/2.0.1/Resources/Localization/M9/NameTables/rnk_original_rdb_matches.csv \
  --fdata-dir /path/to/your/KIDS_PLATFORM_OUNCE \
  --dest UnPack/2.0.1/Resources/Localization/M9/NameTables
```

只有 `rnk_original_fdata_recovery.json` 中的 `verified_native_rnk=true` 才代表 RNK 字节验证成功。即使成功，`semantic_property_name_verified`、`text_fk_verified` 仍保持 false，直到恢复实际脚本及 getter 证据。87,445 条数值候选依然未升级。


## M9.8 / M9.9 验收结果（已在 2.0.1_unpack 实际运行）

- [M9.8 Actions #41954445896](https://github.com/969981/poko_resources/actions/runs/41954445896) **Success**：原始 FDATA 提取器单测与严格缺失报告通过。三条来源状态均为 `ORIGINAL_FDATA_NOT_PRESENT`，`verified_original_rnk_sources=0`，`native_irnk_strings_extracted=0`。这是**流程成功、物理输入仍缺失**，不是 RNK 解包成功。可查看 `rnk_original_fdata_recovery.json` 和 `rnk_recovered_irnk_strings.csv`。
- [M9.9 Actions #41954764327](https://github.com/969981/poko_resources/actions/runs/41954764327) **Success**：继续以原版 `.data` 的三处已验证函数指针槽为起点扫描附近 `ADRP+ADD / ADRP+LDR` 原生静态调用线索，精确指针槽的 `code_reference_candidates=0`。**0 命中不代表没有间接调用**；这更符合通过 vtable/对象指针间接派发的情形，尚不能推断 getter。见 `exefs_descriptor_pointer_slot_xrefs.json/csv`。

M9.9 每个指针槽相邻的 64 位项呈现同一模式，值得下一轮核对 vtable/address-point：

| Hash | `.data` 槽位 | 前一槽 `-0x8` | 后一槽 `+0x8` | 后两槽 `+0x10` |
|---|---|---|---|---|
| `0x0b6e1578` | `0x32ecf60` | `0x1fe4fa0` | `0xca2cf8` | `0xca2d04` |
| `0xe21ff09f` | `0x32fa020` | `0x1fe4fa0` | `0xd38570` | `0xd3857c` |
| `0xf92c5190` | `0x32fdfd8` | `0x1fe4fa0` | `0xd594dc` | `0xd594e8` |

这些属于**原始字节中的相邻代码指针结构**，不能直接叫作已经恢复的 getter vtable；下一步应识别包含该地址点的对象构造与 `[vptr + offset]` 间接派发、验证传入的缓冲区和属性 ID，然后再寻找脚本对 M7 表号与行 ID 的 typed-field 选择路径。87,445 个数值候选及 0 个剧情/任务/建筑外键的未验证状态保持不变。


## M9.10–M9.12：ExeFS 原生 vptr 写入与描述符回调槽（2026-11-05）

这三轮均基于 SHA-256 `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f` 的原版 `2.0.1/exefs/main`，每个新结论都保留准确 PC、源指令及数据地址。

- [M9.10 #41955573731](https://github.com/969981/poko_resources/actions/runs/41955573731) **Success**：针对三组已验证函数槽 `±0x100` 搜索近邻 `ADRP+ADD/LDR`。只在 `0xf92c5190` 邻域找到 3 条地址构造引用：`main+0xD591B8→0x32FDF90`、`main+0xD5962C→0x32FE0B8`、同指令窗口延迟匹配 `0x32FE010`。后者非相邻配对，不能当成稳定数据流。
- [M9.11 #41955853719](https://github.com/969981/poko_resources/actions/runs/41955853719) **Success**：对上述指令窗口逐字节回验并反汇编，捕获对象分配后 `ADRP+ADD+ADD→STP x8,xzr,[x23/x22]` 的实际路径。报告保存为 `exefs_vptr_disassembly_windows.json`。
- [M9.12 #41956233084](https://github.com/969981/poko_resources/actions/runs/41956233084) **Success**：确认两条原生直线数据流的对象 vptr 写入（`main+0xD591C8` 和 `main+0xD59640`）；第一条写入地址 `0x32FDFA0`。核对原生 `.data`，其 `+0x38` 位置为 `0x32FDFD8`，含实际函数指针 `main+0xD59420`，即 M9.5 对 `0xf92c5190` 的描述符填充函数入口。这是**原生对象 vptr 写入 + 回调槽成员身份**的直接证据；不是实际运行时回调、KIDSOBJDB getter、脚本外键的直接证据。第二条写入 `0x32FE0C8`，尚未证明它与本 Hash 的语义关系。

因此证据链已从静态 Hash 常量升级为：

```
main+0xD591B8       ADRP/ADD +0x10 -> x8 = 0x32FDFA0
main+0xD591C8       STP x8,xzr,[x23]（对象首字段 vptr）
0x32FDFA0 + 0x38   -> 原始 .data 函数槽 0x32FDFD8
*(u64*)0x32FDFD8   -> main+0xD59420
main+0xD59420      -> 0xf92c5190 元数据描述符写入
```

证据文件：`exefs_vtable_neighborhood_report.json`、`exefs_vtable_neighborhood_xrefs.csv`、`exefs_vptr_disassembly_windows.json`、`exefs_verified_vptr_stores.json`。其中 `verified_runtime_indirect_dispatchers=0` 和 `verified_native_kidsobjdb_getters=0` 必须保留。

## M9.13：M3 结构字段与 M7 文本表 ID 的负例筛查

[M9.13 #41956641307](https://github.com/969981/poko_resources/actions/runs/41956641307) **Success**。新增 `Scripts/resources/m9_typed_text_tuple_triage.py` 对 **1,176,984 个已验证类型字段、101,467 个对象、195 组 M7 九语言表**做严格编号交叉筛查。规则为：

1. 同一个原生 KIDSOBJDB 对象内的 **4 字节单值**属性，其中某属性的原始 `u32` 数值等于 M7 九语言组起始文件号；
2. 该对象相距不超过 3 个属性位置的另一 `u32` 单值落在该组的非零行号范围。

**结果：0 组**匹配。仅说明此受限的“双单值字段邻接”假设未命中，不排除数组、跨对象关联、其他非 KIDSOBJDB 脚本资源或其他文本解析机制。没有任何剧情/任务/建筑字段名因该扫描获得证明。详情在 `M9/ScriptTextCandidates/m9_numeric_text_tuple_report.json`，空候选 CSV 中保留列结构，既有 M8 的 5,365 条真实来源关联以及 87,445 条未验证 OID 数值候选均保持不变。

## M9.14：`vptr+0x38` 的一般间接调用点扫描

[M9.14 #41956930057](https://github.com/969981/poko_resources/actions/runs/41956930057) **Success**。在原版 2.0.1 ARM64 可执行段中扫描 `LDR [vptr, #0x38] → BLR` 形态，得到：

- `LDR X,[X,#0x38]` 结构性匹配 **28,039** 条；
- 在随后限定窗口内出现同目标寄存器 `BLR/BR` 的候选 **13,800** 个加载点；
- 前一条指令也符合 `LDR vptr,[object,#0]` 的 **2,543** 个加载点；
- 连续三指令 `LDR vptr → LDR [vptr,#0x38] → BLR` 的 **2,285** 个实例。

**这些是真实的通用 ARM64 虚调用结构，但没有一个被证明实际调用 M9.12 的那一个具体对象类**。不能把所有偏移同为 `0x38` 的虚调用算作目标回调。原始字节和最多 700 条上下文样本见 `exefs_virtual_slot_0x38_dispatch_candidates.json`。继续的最短路径是从 M9.12 的两个构造点追踪对象流向哪个注册表／调用者，再与某一个具体 `BLR` 和 `x1/x2/x3` 参数设置建立连续控制流。

RNK 物理文件仍未取得；脚本→M7 正式外键仍 **0**。


## M9.15–M9.17：特定对象构造 → owner+0x28 → 静态虚调用点（2026-11-05）

三阶段均基于原始 2.0.1 NSO SHA-256 8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f，原始 PC、机器码、寄存器和指针见 NameTables 下相应 JSON。

- [M9.15 #41957811298](https://github.com/969981/poko_resources/actions/runs/41957811298) **Success**：对象从 x0 保存到 x23（main+0xD591B0），写入已验证 vptr（main+0xD591C8），并经 **main+0xD59274: str x23,[x19,#0x28]** 保存到持有者成员，中途无 x23 寄存器覆盖。定位 +0x28 成员读取 28,569 处、限定窗口里符合“成员→vptr→+0x38→BLR”形态 106 处，连续四指令形态 5 处；**同偏移不同类，不能直接认定为目标描述符调用**。证据：exefs_owner_0x28_escape_trace.json。
- [M9.16 #41958058637](https://github.com/969981/poko_resources/actions/runs/41958058637) **Success**：限定原生代码 main+0xD57C00..0xD59C00 分析，构造侧 main+0xD590FC: mov x19,x3；清理侧 main+0xD58E54: mov x19,x3。相同参数位置与相同 +0x28 成员显示明确的本地对象生命周期关系候选。此局部范围直接 BL 入边为零，不排除间接调用。证据：exefs_owner_x19_local_callgraph.json。
- [M9.17 #41958409303](https://github.com/969981/poko_resources/actions/runs/41958409303) **Success**：严格确认原生静态调用点 main+0xD58F10: BLR x8，其 x8 经 x23→对象 vptr 首槽加载，且 x23 从 owner+0x28 取得。持有者成员在末尾被清空。证据：exefs_owner_specific_virtual_slot0.json。

### 逐字节核验的两条函数路径

**构造并持有：** main+0xD590FC (mov x19,x3) → main+0xD591B0 (mov x23,x0) → main+0xD591C8 (stp x8,xzr,[x23]，x8=0x32FDFA0) → **main+0xD59274 (str x23,[x19,#0x28])**。

**读取、间接调用及清空：** main+0xD58E54 (mov x19,x3) → main+0xD58EB8 (ldr x23,[x19,#0x28]) → main+0xD58F04 (ldr x8,[x23]) → main+0xD58F08 (mov x0,x23) → main+0xD58F0C (ldr x8,[x8]) → **main+0xD58F10 (blr x8)** → main+0xD58F28 (str xzr,[x19,#0x28])。

| 已知类的虚表槽 | 物理地址 | 原始函数地址 | 证据含义 |
|---|---|---|---|
| vptr+0x0 | 0x32FDFA0 | main+0xD593CC（入口为 RET） | 同 +0x28 位置对象有真实 slot 0 间接调用代码 |
| vptr+0x38 | 0x32FDFD8 | main+0xD59420（描述符 Hash 0xf92c5190） | 原始槽与函数已证实，但尚缺此特定类的 slot +0x38 调用者 |

**限制：** 两个函数的 owner 均来自 x3 且成员偏移相同，仍没有动态证据确认运行时传入的是同一个持有者实例；实际 BLR 目标仅在虚表未改写且为已知类时可静态解析。M9.17 证明了具体指令点和类虚表首槽的原生字节，不证明游戏运行时调用记录，更不证明 slot+0x38 的描述符消费者、KIDSOBJDB getter 或剧情/任务/建筑 M7 外键。正式新增这些外键 **0**。

下一阶段优先追上层 x3 参数／注册表中对象类型身份，闭合实际 **vptr+0x38** 消费路径，再由 Native getter 与 M7 行号进行对账。原始 RNK 的 3 份 FDATA 物理数据依然缺失，不能伪造 IRNK 字符串。


## M9.18：精确入口在原生 .data 的双回调指针表位置（2026-11-05）

[M9.18 #41958960997](https://github.com/969981/poko_resources/actions/runs/41958960997) **Success**。不再扩大全局 BLR，而是以 M9.16/M9.17 逐字节确认的两个函数入口为目标，扫描原版 NSO 的非文本数据段中精确 64 位指针。

| 函数 | 已确认 PACIBSP 入口 | 原始 .data 指针地址 | 同一地址邻域 |
|---|---|---|---|
| 持有者清理/消费回调 | main+0xD58E34 | 0x32FDE38 | +8 main+0xD58F50，+0x10 main+0xD58F58 |
| 持有者构造/填充回调 | main+0xD590E0 | 0x32FDF38 | +8 main+0xD592B4，+0x10 main+0xD593AC |

**两个入口都在原生 .data 中找到精确 qword，位置相差 0x100 字节**。两处静态指针块相邻且共享若干外部函数指针布局，增强了“相关虚回调接口”的结构假设，但尚未通过实例 vptr、注册器构造和 x3 实参证明它们运行时属于同一类／同一 owner。报告 exefs_owner_two_callback_pointer_tables.json 中仍保持 registered_dispatch_consumer_proven=false、same_runtime_owner_type_proven=false。

M9.17 的具体静态间接调用点 main+0xD58F10/slot0 已闭合到 owner+0x28；**目标描述符 slot+0x38 的实际调用点仍未闭合**。RNK 三个 FDATA 物理来源与脚本→M7 外键状态也保持未完成，不能升级证据。

## M9.19–M9.22 — 回调表、完整函数体与真正的 `+0x38` 接收者（2026-11-05）

### M9.19 — 静态回调槽不等于已经证明的 vptr

- [Actions #41962144836](https://github.com/969981/poko_resources/actions/runs/41962144836) **Success**。两组原生 .data 指针 `0x32FDE38→main+0xD58E34`、`0x32FDF38→main+0xD590E0` 逐字节验证。
- 假设各回调均位于其 vptr+0x38，则推得两个候选 vptr `0x32FDE00`、`0x32FDF00`。完整原生 code 的精确 ADRP+ADD（含相邻 ADD）引用结果 **0 条**。此负例不能排除间接登记，但不能认定派生地址点为真正 vptr。
- 文件 `exefs_owner_callback_vptr_base_probes.json`。

### M9.20 — 两组静态回调表的 12 个邻近函数

- [Actions #41962522416](https://github.com/969981/poko_resources/actions/runs/41962522416) **Success**。首次 [#41962440001](https://github.com/969981/poko_resources/actions/runs/41962440001) 失败原因仅为三条 LDR 解包错误及合成测试表缓冲区不足，已经修复。首次失败未形成原生数据结论。
- 构造回调表 `0x32FDF38→main+0xD590E0` 的相邻函数槽 `0x32FDF40→main+0xD592B4` 已确认；它从 x3 取得持有者。
- 第一版分析遇到 ARM64 跳转表 `BR x9` 会提前停止，故不能用第一版的 0 个连续 +0x38 调用形态宣布全函数没有消费者。文件 `exefs_owner_sibling_callback_consumers.json`。

### M9.21 — 四个限定函数体全量反汇编

- [Actions #41962777294](https://github.com/969981/poko_resources/actions/runs/41962777294) **Success**。限定 `0xD58E34..0xD58F50`、`0xD58F60..0xD58FF4`、`0xD590E0..0xD592B4`、`0xD592B4..0xD593AC` 四段，恢复 **287 条原生指令**，其中 x3→x19 有 3 处，owner+0x28 成员读取 4 处，跳转表 BR 3 处。
- 构造侧第二回调 `main+0xD592B4` 中，`main+0xD59310` 和 `main+0xD59340` 读取 `[x19+0x28]`；`main+0xD59364..D59370` 经 vptr 首槽作 BLR，`main+0xD59388` 清空持有者成员。这支持与 M9.17 相似的对象生命周期结构，但同一运行时实例未验证。
- 原始字节、全部指令与分支结构：`exefs_owner_complete_callback_control_flow.json`。

### M9.22 — `main+0xD59250` 是 x22 的 +0x38 调用，并非已知内部 x23 对象

- [Actions #41963059933](https://github.com/969981/poko_resources/actions/runs/41963059933) **Success**。原始 NSO、M9.21 指令 SHA/机器码交叉校验，关键数据流如下：

```asm
main+0xD591A0  mov x22, x0          ; 保存第一对象
main+0xD591A4  ldr x8, [x0]
main+0xD591A8  ldr x8, [x8, #0x30]
main+0xD591AC  blr x8              ; 返回值在 x0
main+0xD591B0  mov x23, x0         ; 第二个对象的来源
main+0xD591C8  stp x8, xzr, [x23] ; 赋已知内部 vptr 0x32FDFA0
...
main+0xD59240  mov x0, x22
main+0xD59244  ldr x8, [x22]       ; 当前 this 为 x22
main+0xD5924C  ldr x8, [x8, #0x38]
main+0xD59250  blr x8
main+0xD59274  str x23, [x19, #0x28]
```

- 已验证 x22、x23 在关键区间无寄存器重赋值，二者来源分别是第一次虚调用前的 x0 与调用后的 x0。**来源不同不等于运行时指针一定不相等。**
- **关键否定证据**：此前看见的 `vptr+0x38` 调用实际上从 **x22** 读取虚表，而已知 `0x32FDFA0` 的 vptr 被写入新对象 **x23**。因此 **不能把 `main+0xD59250` 的 BLR 认定为 `main+0xD59420` 描述符回调成功调用**。
- 文件 `exefs_constructor_slot38_receiver_provenance.json`。

**当前边界：** 已证实回调表、各自函数体、x3→owner+0x28 的局部路径、slot0 静态间接调用，以及一次接收者为 x22 的 slot+0x38 指令。尚未证实特定内部 x23 的 slot+0x38 消费者、相同 x3 实例的上层真实调用者、KIDSOBJDB getter 或剧情任务建筑到 M7 的正式新外键（仍 0）。物理 `0xea42a223.fdata`、`0x5c83387f.fdata`、`0x898afd6d.fdata` 仍缺失，RNK/IRNK 不能由 Hash 推断生成。`main` 不受影响。

## M9.23 — 只读 GDB 运行时目标回调证据采集（2026-11-05）

[Actions #41963759345](https://github.com/969981/poko_resources/actions/runs/41963759345) **Success**：此 CI 仅验证 Python 语法和合成记录的边界条件，**没有运行 Switch2 游戏或真实 GDB 会话，不能写成运行时 callback 验证通过**。

### 精确采集点

只在已取得 NSO 字节证据的入口／代码位置设断点：`main+0xD590E0`（构造回调）、`+0xD591C8`（内部对象 vptr）、`+0xD59274`（owner+0x28 保存）、`+0xD58E34`（清理回调）、`+0xD58F10`（slot0 BLR）、`+0xD592B4`（同表相邻回调）、`+0xD59250`（接收者 x22 的 slot+0x38）、`+0xD59420`（目标内层类描述符回调）。

脚本 `Scripts/resources/m9_gdb_owner_callback_trace.py` 实现只读寄存器／内存回读、每点最多 24 次命中并自动继续、JSONL 事件记录；不写游戏内存、不修补二进制。另提供不依赖 GDB 的 `Scripts/resources/m9_runtime_callback_trace_validator.py`，检查用户采集日志中的 main 基址、PC、x0 vptr、vptr+0x38 真实目标以及从 LR-4 读取的原生 BLR 指令候选。

### 使用方法

先确保游戏确为本次研究的原版 2.0.1 NSO，SHA-256 为 `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`。打开连接目标 ARM64 的 GDB，并取得**运行时实际 main 装载基址**（不是文件偏移，也不是预先猜出的地址）：

```gdb
source -s python Scripts/resources/m9_gdb_owner_callback_trace.py
m9trace-install 0xACTUAL_MAIN_LOAD_BASE ./m9_23_trace.jsonl 24
continue
```

在用户本地退出调试后，执行：

```bash
python Scripts/resources/m9_runtime_callback_trace_validator.py --input m9_23_trace.jsonl --output m9_23_report.json
```

**严格验收区别：**

- 如果 `main+0xD59420` 实际命中，且当时 `x0.vptr == actual_main_base + 0x32FDFA0`、`*(x0.vptr+0x38) == actual_main_base + 0xD59420`，则形成 **同类实例上的实际描述符函数入口命中证据**。如果另见 LR-4 是 ARM64 BLR，可定位候选上层间接调用点；还需要对调用者寄存器／虚表槽读取进行实证，才能宣布特定 slot+0x38 派发闭合。
- 如果只看到 `main+0xD59250` 命中，按 M9.22 的证据它属于 x22 接收者，**不得写成内部 x23 描述符调用成功**。
- 捕获同一个 x3 数值出现在构造和清理回调只是**运行时地址一致的候选**，还应排除对象生命期结束后地址重复利用。没有日志时不许猜测。
- 用户未提供真实运行日志，当前 `specific_vptr_slot0x38_indirect_call_path_proven=false`、原生 `RNK/IRNK` 名称为 0、新正式 M7 剧情／任务／建筑文本外键为 0，保持不变。
