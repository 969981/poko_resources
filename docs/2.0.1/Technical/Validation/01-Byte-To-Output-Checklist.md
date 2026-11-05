---
title: 源字节到导出产物的验收清单
tags: [pokopia, 2-0-1, validation, provenance]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 字节 → 记录 → 转换 → 导出：最小验收清单

## 建议统一的 provenance 记录字段

| 字段 | 含义 | 缺失时的处理 |
| --- | --- | --- |
| `game_version, source_path` | 2.0.1 版本、仓库相对原始路径 | 不能发布为可复现数据 |
| `source_sha256, source_size` | 针对 **文件字节** 的校验 | 标记来源未验证；不要改用 Git blob SHA 冒充 |
| `container_entry, record_index, byte_offset` | LINKDATA / RDB / TEXINFO / 原生数据具体位置 | 不能宣称已完成字段级追溯 |
| `raw_value_hex, decoder_version` | 原始字节、解包/解码器提交标识 | 保留未解释字段为 UNKNOWN |
| `conversion_params` | swizzle、BC7/G1T 格式、UV、文本 UTF-8 规则等 | 输出仅作候选，不可作验收图 |
| `output_path, output_sha256, status` | 导出和回读校验 | 不可标记转换完成 |
| `identity_evidence, negative_cases` | 游戏 ID / 外键代码消费链、反例 | 结论保持 CANDIDATE / UNKNOWN |

## 按数据类型的门禁

**LINKDATA / RDB / FDATA**

- 确认索引号、FDATA 容器是否存在、目标记录物理边界与解压后长度。
- `INDEXED`、`EXTRACTED`、`DECODED`、`VERIFIED` 必须分开；不满足时保留错误码与原字节，不吞异常。

**TEXINFO / G1T / PNG**

- 检查 TEXINFO count 与每条 104 字节记录边界；G1T texture count、像素格式与平台值。
- 验证 TEXINFO→G1T 的**引用关系**，再核对 layer、UV、swizzle、BC7 解码和 PNG SHA。
- 主图集源验证依据：[item_atlas_1333_uv.csv](../../../../UnPack/2.0.1/Resources/Textures/Indexes/item_atlas_1333_uv.csv)，在上游索引里部分条目仍明确标注 `PIXELS_UNVERIFIED`；最终以实际 PNG manifest 和视觉抽样为准。
- 绝不把第三方对照图片视为原生文件，也不把宝可梦贴图编号当物种 ID。

**原生文本 / CSV / JSON**

- 确认记录宽度 8 或 32、相对指针目标、NUL 终止、严格 UTF-8、控制符与私用区字形保留。
- 每条语言记录保留 table entry、row ID、form index、原始位置；按九语言结构验证，不将“同一行”推断成“任务外键”。
- 用 [00983 验证报告](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/validation.json) 单独验物品名称，但仍不能证明材料类型与堆叠上限。

**SQLite / 批量索引**

- 标明主键、关联键证据类型（真实引用/哈希匹配/数值候选）、唯一性、缺失数；不能让仅数值相等的候选自动变成外键。
- 对每个 CSV/JSON/SQLite 导出保存行数、列名和输入哈希；重导出应有差异报告。

## 验收结果填写模板

~~~yaml
game_version: "2.0.1"
source_path: "<repo-relative-source>"
source_sha256: "<64-hex-or-UNKNOWN>"
container_entry: "<entry-or-NA>"
record_index: "<zero-based-or-NA>"
byte_offset: "<absolute-integer>"
parser: "<repository-relative-script>"
conversion_params: {}
output_path: "<repo-relative-output>"
output_sha256: "<64-hex-or-UNKNOWN>"
parse_status: "DECODED|FAILED|UNVERIFIED"
identity_status: "VERIFIED|CANDIDATE|UNKNOWN|DISPROVED"
negative_cases: []
checked_at: "<ISO8601-local>"
~~~

相关：[[docs/2.0.1/Technical/Samples/README|真实 Hex 样本]] · [[docs/2.0.1/Technical/08-Evidence-And-Open-Questions]]。
