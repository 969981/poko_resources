# M9.3–M9.5 — KIDSOBJDB `_RNK0000` 名称资源与原版 ExeFS 属性 Hash 消费证据

分支：`2.0.1_unpack`。**状态：原生名称资源的预期身份已恢复，但对应 `_RNK0000` 二进制在仓库现有 M3/FDATA 资源范围内缺失。ExeFS 的 3 条 Hash→字符串元数据构造路径已取得指令级证据，仍不能推断剧情、任务、建筑的文本外键。**

## M9.3：头部自带配套名称表的 Hash

对 M9.2 已逐字节验证的三份原生 KIDSOBJDB，读取 `_DOK0000` 文件头 `u32@0x14`，不是在属性值中猜名称：

| 原始 KIDSOBJDB 资源 Hash | 原生名称资源 Hash | 本仓库 M3 索引与已跟踪 FDATA | 对应 IRNK 字符串 |
|---|---|---|---|
| `d14d76ef` | `aa91cb96` | 0 匹配 | 未取得 |
| `cfd2bd1f` | `a91711c6` | 0 匹配 | 未取得 |
| `b290631c` | `cb3c8b15` | 0 匹配 | 未取得 |

核对 89,507 条 M3 资源索引后，三组均为 `RNK_NAME_FILE_MISSING`。这是**当前仓库输入未找到匹配的名称文件**，并非断言整个游戏或其他版本必然不存在。不得因此自动生成或填入名称。

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
