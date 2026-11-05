# M9 — M3 KIDSOBJDB 对象与 M7 九语言引用关系

本目录是 Pokopia 2.0.1 原生数据的**来源证据图**，不把未确认的资源字段、文本 ID 或脚本调用关系伪装成已解码。

## 已完成（原生文件与来源可核验）

- 从 `UnPack/2.0.1/_reports/m3_resource_type_index.csv` 流式读取 M3 资源身份和 SHA-256；关联三个 `KIDSOBJDB_SIGNATURE` 样本 `b290631c`、`cfd2bd1f`、`d14d76ef`，而不是按名字相近猜测身份。
- 读取最新的 `M7/nine_language_groups.csv`，验证核心锚点 `2323`、`2350`、`3304`、`4645`，避免锁死旧分组统计。
- 将 M8 经原生记录格式和 PokoHex 固定源码证明的外键导入 `verified_resource_text_edges.csv/json` 以及 `localization_reference_graph.sqlite`：
  - `Item → ItemName`
  - `MapPartVariation → Part → Item → ItemName`
  - `Reaction/Skill ID → 对应语言表的同编号记录`
- 输出 `m3_object_sources.csv`（原始 FDATA、M3 record、name/type hash、解码结果 SHA-256）、`m3_object_node_signatures.csv`、`m3_literal_markers.csv`、`unverified_numeric_candidates.csv`。
- 严格隔离未验证整数：`candidate_numeric_matches.is_verified_fk = 0` 受 SQL CHECK 约束；即使某对象字节碰巧等于 M7 表号，也不是可用外键。

## M9.1：KIDSOBJDB 原生记录边界

对于已确认的 `_DOK0000` 容器：

- 头部 `u32@0x08=28`，`u32@0x0C=24`，`u32@0x10=记录数量`，`u32@0x18=容器字节数`。
- 从 `0x1C` 开始，原生记录以 `IDOK0000` 为标记，`u32@(record_start+0x08)` 给出包括头部的记录长度；下一条从 `align4(record_start+length)` 开始。
- 严格校验标记、跨度、零填充、记录数量和最后的文件大小，并计算每条原始记录的 SHA-256。
- `record_start+0x0C` 至 `+0x1C` 的 5 个 `u32` 作为**未命名原始字段**导出，不能擅自将其中任一个称为场景、任务、文本表 ID。
- 逐条导出 `Objects/m3_kidsobjdb_native_records.csv`，以及 `Objects/m3_kidsobjdb_native_framing.json` 与 `Objects/m9_object_framing_report.json`；并在 SQLite 增加 `m3_kidsobjdb_records` 表。

具体的记录边界验收以 [M9.1 Actions](https://github.com/969981/poko_resources/actions/workflows/unpack-m9-kidsobjdb-framing.yml) 成功运行的实际报告为准。未成功验收前不能声称已完成全部对象解析。

## 当前真实边界与下一步

**已有的直接外键主要来自 M8 的 Item/MapPart/Reaction/Skill 布局**。KIDSOBJDB 记录边界虽然可恢复，但其原生字段的实际含义、任务配置的唯一身份以及脚本的资源获取 / 调用者并未证明。因此以下语义暂时不得启用：

- `MissionSettings/Quest/Dialogue/Buildings/UI/Tutorials` 对 M7 的映射；
- 任意根据文本关键词、容器序号、`name_hash` 与 `type_hash` 直接填充的功能分类；
- 将未经确认的 IDOK 原始字段视为文本资源外键。

最终所需证据链必须包含 **caller 源文件／对象身份 + typed field（含原始偏移、格式与 ID 域）+ M7 文本表引用 + 原生行 ID + 九语言文字**。必须先恢复 KIDSOBJDB 对象成员的序列化格式或对应的 `bfbs/Lua/ExeFS` 消费端，才能把本目录的 UNKNOWN 类别升级为正式类别。

## 工作流

- [M9 资源引用图](https://github.com/969981/poko_resources/actions/workflows/unpack-m9-caller-refs.yml)
- [M9.1 原生 KIDSOBJDB 记录](https://github.com/969981/poko_resources/actions/workflows/unpack-m9-kidsobjdb-framing.yml)

只读原始文件；提交的是索引、证据、SQLite 和失败诊断，不会覆盖 RomFS。


## M9.2 — 实际原生属性恢复结果（2026-11-05）

[GitHub Actions 成功运行 #41949211644](https://github.com/969981/poko_resources/actions/runs/41949211644)，已从 M3 原始文件和 KIDSOBJDB 官方格式兼容的开源解析布局中恢复了 **1,176,984 条逐属性记录**，记录原始 `object_id`、`object_type_hash`、`property_name_hash`、数据类型（整数／浮点／向量）、数组元素数量、数据字节偏移、长度和 SHA-256。所有属性值精确填满其各自的原生 IDOK 记录，没有越界、跳槽或强行按字符串猜 ID。

| M3 来源 | 已校验对象 | 恢复属性数量 | 仅数值匹配的局部对象 ID 候选 |
|---|---:|---:|---:|
| `b290631c` | 31,740 | 247,598 | 12,510 |
| `cfd2bd1f` | 1,330 | 17,740 | 1,228 |
| `d14d76ef` | 68,397 | 911,646 | 73,707 |
| **合计** | **101,467** | **1,176,984** | **87,445** |

重要证据区分：

- `NATIVE_TYPED_PROPERTY_BOUNDS_EXACT`：原始属性描述、类型、数值范围和 SHA-256 已按原生字节证实。
- `TYPED_U32_EQUALS_LOCAL_OID_UNVERIFIED_REFERENCE`：属性的 u32 值恰好命中同库唯一对象 ID，**仍不代表已经证明的对象调用关系**。
- 目前尚未恢复对应游戏版本的 `.name` 成员名表，也没有足够的脚本 / ExeFS 消费端引用确认这些属性 Hash 所代表的业务语义。
- 不能把上述 87,445 个候选或对象序号写入 M7 的正式 `text_id` 外键。新确认的剧情／任务／建筑文本外键仍为 **0**。

原始属性 CSV 采用 24 MiB 左右的分片避免 GitHub 单文件 100 MiB 限制。输出目录为 [`M9/Properties`](./Properties)，主要文件包括 `native_typed_fields_*.csv`、`unverified_local_oid_candidates_*.csv`、`m9_typed_field_report.json`。

解析参考为 [eArmada8 / yumia_decode_kidsobjdb](https://github.com/eArmada8/yumia_fdata_tools/blob/9d8dc1fb7436f14ffec42acb6d719cea1214abbd/ktid/yumia_decode_kidsobjdb.py) 与 [PieceMetal / KidsObjectDatabase](https://github.com/PieceMetal/DWOriginsAssetTool/blob/22d744f37d4a55a7b684bd8c6d7fd14665c0152d/Core/KidsObjectDatabase.cs)，并由本项目真实 2.0.1 文件验收。

## M9.3～M9.5 — `_RNK0000` 名称资源 Hash 与 ExeFS 消费证据（2026-11-05）

已完成三轮原版 2.0.1 数据分析（Actions [M9.3 #41951158981](https://github.com/969981/poko_resources/actions/runs/41951158981)、[M9.4 #41951784826](https://github.com/969981/poko_resources/actions/runs/41951784826)、[M9.5 #41952223555](https://github.com/969981/poko_resources/actions/runs/41952223555) 全部成功）。

从三个 `_DOK0000` 头部 `u32@+0x14` 恢复的配套 `_RNK0000` 名称资源 Hash 分别为 `aa91cb96`、`a91711c6`、`cb3c8b15`。现有 89,507 条 M3 索引和已跟踪相关 FDATA 路径里没有找到匹配的真实 `_RNK0000` 文件，**RNK 字符串尚未恢复**。

另一方面，原版 ExeFS 在 3 处地址构建了属性 Hash 并通过两次同址相邻 `STP` 把 Hash 与 rodata 字符串指针写入同一个描述符路径：

- `main+0xCA2C80`：`0x0b6e1578` ↔ `DisplaysetObjectNameHash`
- `main+0xD38530`：`0xe21ff09f` ↔ `ObjectNameHashArray`
- `main+0xD59460`：`0xf92c5190` ↔ `TexturesRenderStateObjectHash`

它们是 **ExeFS 指令级 Hash/字符串元数据关联候选**，不是已取得 RNK 表的属性名称，也不证明游戏实际 KIDSOBJDB getter 读取了对应字段。其余 87,445 条 `u32==local OID` 候选全部维持未验证，剧情/任务/建筑文本正式外键仍为 0。详细证据、字节偏移、完整 ARM64 反汇编、CSV/JSON 和核验入口见 [`NameTables/README.md`](./NameTables/README.md)。
