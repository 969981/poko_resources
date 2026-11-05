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
