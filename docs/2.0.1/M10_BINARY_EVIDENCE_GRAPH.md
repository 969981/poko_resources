# M10 — Pokopia.Binary 原始 RDB/FDATA 批量对账与 KIDSOBJDB 物品字段候选关系图

## 目标与数据边界

延续 M9 和 Pokopia.Binary Phase 2。现有 Python 原生解包、纹理解码、九语言整理、CSV/SQLite 和原始证据校验链不整体迁移。新增 C# 原始索引头批量审计，以及由 Python 汇聚的可查询 SQLite 证据图。

**不得混淆以下三层：**

1. `NATIVE_TYPED_PROPERTY_BOUNDS_EXACT`：已解码原始 KIDSOBJDB IDOK 属性宽度与位置。
2. `NUMERIC_EQUALITY_UNVERIFIED` / `SCALAR_U32_EQUALS_ITEM_ID_UNVERIFIED`：原始数值相同，只是无语义关联候选。
3. `CONFIRMED_NATIVE_FK`：必须有原生消费者基址、字段名 / schema、正反例对应，当前为 **零**。

## A. 大规模原生资源定位

独立的 `Pokopia.Binary.Cli` 提供：

```bash
dotnet run --project Pokopia.Binary.Cli -c Release -- audit-fdata-summary 2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdb 2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdx 2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE
```

输出包含原始 RDB 索引总行数、已对齐的 FDATA IDRK 头数、未获取的物理 FDATA、未知尾部与不匹配数量、耗时、证据样本。仅在当前 checkout 确实含有相应原始 FDATA 时，才会取得有效头部匹配。分卷 `.7z.001` 不能当作原生 FDATA 直接验证；CI 的缺失结果表示当前检查样本范围受限，**不是**格式错误或资源不存在。该功能无 Oodle 解压、无原始数据提交、无资产拷贝。

使用 `root.rdb/root.rdx` 与 `system.rdb/system.rdx` 两套真实索引，原始文件来自 `2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/`。CI 在原始单文件 FDATA 和一部分 MountPoint 资源上做物理命中验证，不把所有缺失条目记为通过。

## B. 可查询的对象字段与物品 ID 关系图

```bash
python -m Scripts.resources.build_binary_evidence_graph --output /tmp/m10-graph
```

验证原始 `00983.bin` SHA、4,600 条 × 68 字节、记录 ID 与 `+0x22` 名称索引，导入经 M9 审计的三份 KIDSOBJDB 字段样本数据。CSV/SQLite **仍由 Python 负责**。

SQLite 结构：

- `item_records`：物品 ID、来源 983、绝对文件偏移 `64+68*id`、记录 SHA256、名称索引、原始 `0x26 / 0x3a / 0x08` 字段；只将 NameIndex 标为已证实。
- `kids_sources`、`kids_nodes`、`kids_fields`：来源作用域、原始节点偏移 ID、原始 U32 字段与属性 Hash、属性值的字节位置、长度和 SHA。原始 `node+12` 的 OID 语义仍属于候选。
- `local_oid_equalities`：经字段边界、原始属性 Hash、源节点 raw U32 和目标节点 raw U32 重新交叉核对的 M9 同源数值相等候选；**不是**已证实的对象引用。
- `item_id_equalities`：类型 4/5、单元素 U32 与一条有名称的原始物品 ID 数值相同，且保留原始字段偏移与 Hash。可能大量误命中，**不得**直接用它给游戏物品分类、材料、任务解锁或制作需求贴标签。

查询候选字段，按物品出现覆盖从高到低：

```sql
SELECT property_hash, COUNT(*) AS raw_matches,
       COUNT(DISTINCT item_id) AS distinct_item_ids
FROM item_id_equalities
GROUP BY property_hash
ORDER BY distinct_item_ids DESC, raw_matches DESC
LIMIT 30;
```

追踪一个有名称物品的全部候选字段来源：

```sql
SELECT i.item_id, i.en_name, i.record_offset,
       e.source_id, e.node_index, e.property_hash,
       e.value_absolute_offset, e.evidence
FROM item_records i
JOIN item_id_equalities e ON e.item_id=i.item_id
WHERE i.item_id=107
ORDER BY e.source_id, e.node_index, e.property_hash;
```

## 证据状态与下一步突破

`+0x26` 和 `+0x3a` 均为原始候选分类字段，未取得原生消费代码证明；不能将 `0x10` 正式命名为游戏材料类型。逐物品最大堆叠量仍未知；存档字节上限 255、玩家常见的 99、背包槽位是不同概念。

**真正的语义突破必须回到 ExeFS main**：从 `00983.bin` 的原生解析/加载器确定 68 字节基址，再回溯 `+0x26`、`+0x3a` 对应的消费者、数组分发和 UI/制作使用路径；堆叠需要检查入包合并、拆分、保存与拒绝分支。不具备基址数据流和正反例时保持 `UNVERIFIED`。

## CI 与交付

`.github/workflows/pokopia-binary-m10.yml` 的两项独立 Job：
1. 对真实 root/system RDB/RDX 全量索引和当前仓库可直接读取的原始 FDATA 批量审计，并归档 JSON。
2. 对全部 M9 字段/边候选 CSV 生成 SQLite，核对原始数量与外键完整性，并归档 SQLite、统计 JSON 和属性哈希候选榜。

使用 Actions artifacts 归档，**不**把可能数百 MB 的 SQLite 直接提交 Git 分支。实际验收须读取当次 run 的日志及报告；工作流显示成功不等于存在已验证的物品语义外键。
