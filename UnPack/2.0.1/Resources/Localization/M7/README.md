# M7 — 原生文本表 ID 与九语言结构关联

## 状态与范围

从 Pokopia 2.0.1 `UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/*.bin` 读取**真实原始解码字节**，恢复文本表记录编号、字节偏移、文本（保留控制标签）和原始元数据，并谨慎关联连续九语言文件。该工作流**不修改游戏文件**。

这不是“剧情 / 任务 / 建筑完整九语言已验证”的声明。数据库中 `text_id` 是 **zero-based native table record ordinal**；独立场景或 Lua/任务标识是否引用相同 ID，需要进一步恢复对象/脚本引用链。

## 已观察并用原生文件验证的结构

- 文件前 64 字节是头部：`u32 count`，另有 `u32 header_version` 及保留字段（以下样本可见其余 56 字节为 0）。
- **普通表**：`count * 8` 字节索引。每条 8 字节：`u32 relative_offset`、`u32 raw_flags`。
- **多形态表**：`count * 32` 字节索引。每条 32 字节：6 个 `u32 relative_offset`，随后 2 个原始 `u32 metadata`；6 个原始形态槽不能未经证据推断为全部语言共用的语法规则。
- 每个 offset 相对于**该指针字段自身的文件偏移**：`string_absolute_offset = pointer_field_byte_offset + u32_relative_offset`，文本 UTF-8 NUL 终止，可能为空。
- 已对 `02324.bin` (515 × 8)、`02351.bin` (248 × 8)、`03305.bin` (10 × 8)、`04645/04646/04653.bin` (3001 × 32) 的所有指针做范围与文本样本检查。

## 九语言顺序及真实基准组

顺序：`jp, en, fr, it, de, es, zht, ko, zhs`。

| 原生文件组 | 条目数 | 记录结构 | 状态 |
|---|---:|---|---|
| `02323.bin`～`02331.bin` | 515 | 8 字节 | 已采样结构/空槽/标志一致 |
| `02350.bin`～`02358.bin` | 248 | 8 字节 | 已采样结构/空槽/标志一致 |
| `03304.bin`～`03312.bin` | 10 | 8 字节 | 已采样部分成员；工作流完成后以完整九份检测为准 |
| `04645.bin`～`04653.bin` | 3,001 | 32 字节 | 已采样语言与相对指针结构；该表不是 4,600 槽道具表本身 |

M7 输出组仅在 9 份连续文件的 **count + stride + 完整非空记录位图 +（8 字节布局的）原始标志序列**完全相同时联接。连续相同结构超过九份时不擅自拆组。统计日语假名、韩语谚文、中文汉字作为额外**文字脚本证据**（不能等价于完整语种验证）。弱组标记 `STRUCTURE_ONLY`，强组标记 `STRUCTURE_AND_SCRIPT_WITNESS`；未匹配记录为 `UNLINKED_NATIVE_RECORD`。

## 重建

```bash
python -m unittest discover -s tests -p "test_m7_localization.py" -v
python Scripts/resources/recover_native_text_ids.py \
  --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded \
  --dest UnPack/2.0.1/Resources/Localization/M7
```

GitHub Actions 入口：`.github/workflows/unpack-m7-localization.yml`。生成文件（以实际成功运行结果为准）：

- `native_table_inventory.csv`：逐原始文件状态、SHA、count、布局、空槽与标志指纹；
- `native_records_000.csv` 等：原生记录 ID、形态 ID、绝对字节偏移、flags、文本及来源；
- `nine_language_groups.csv`：候选的连续九语言组、语种次序、证据等级；
- `nine_language_records_000.csv` 等：同原生表内 ID 的九语言字段、来源文件号、偏移；
- `ambiguous_runs.csv`：长于九份的连续同结构组等歧义；
- `m7_report.json`：统计、锚点组完整性、已知限制。

输出按约 32MiB CSV 分片，避免单个 Git blob 过大，原始解包目录不发生重排。

## 尚缺的第三类证据：功能分类

下一步须从游戏脚本、Lua 参数、对象/资源引用中恢复 `caller/resource hash → text table entry → row index`。在此之前 `category=UNKNOWN`，不能凭关键词自动标为 Dialogue / Quest / Buildings / Tutorials / UI。原生表的相对偏移与“表内记录 ID”虽然已定位，但 **资源级外键** 尚未建立。
