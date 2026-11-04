# Pokopia 2.0.1 — 完整解包验收状态（2026-11-04）

目标分支：`2.0.1_unpack`，最终产物：`UnPack/2.0.1`。本文件按真实 Actions 与文件产物更新，**不能将已存在的解码负载与所有语义资源已转换混为一谈**。

## 已实测且完成的范围

| 阶段 | 数据 | 结果 | 证据 |
| --- | ---: | --- | --- |
| M0 输入校验 | 99 原始文件、10 组分卷 | 实际已供给的原始输入 7z 恢复与校验完成 | [Run #41825954077](https://github.com/969981/poko_resources/actions/runs/41825954077) |
| M1 LINKDATA | 12,298 索引 | 9,793 发布负载，2,505 空索引，0 个未发布的非空记录 | [source_coverage.json](../../UnPack/2.0.1/_reports/source_coverage.json) |
| M2 root + system | 85,832 RDB 索引 | 79,714 条具备物理输入的记录全部已提取/验证，6,118 条因原始输入缺失无法获得 | [Run #41847040530](https://github.com/969981/poko_resources/actions/runs/41847040530) |
| M2 Git 存储完整性 | 89,507 已发布记录 / 18,375,770,432 字节 | 路径缺失 0、文件尺寸不匹配 0、未登记的输出文件 0 | [Run #41837368221](https://github.com/969981/poko_resources/actions/runs/41837368221) |
| M3 前缀分类 | 92,012 索引 | 29/29 源容器扫描成功；89,507 负载扫描，2,505 空索引；0 错误 | [Run #41847881448](https://github.com/969981/poko_resources/actions/runs/41847881448) |
| M3 native 类型 | 89,507 个已发布负载 | 7,377 Magic + 类型哈希双证据确认，72,337 类型仅根据外部 KTID 映射推断，9,793 LINKDATA 未识别 | [Run #41849024461](https://github.com/969981/poko_resources/actions/runs/41849024461) |
| M3 native 重组 | 可检验的 `.bin` 和 `.partNNNN` | 跨文件重组与 SHA-256 工具、39 项单元测试、真实 96 字节 `.kidsobjdb` 导出与 SHA256 成功 | [Run #41849992508](https://github.com/969981/poko_resources/actions/runs/41849992508) |

上述完成意味着**当前提供的 M1/M2 输入均已正确导出且已提交**，以及 M3 文件头/类型索引完成。并不意味着所有数据库字段、模型网格、材质、贴图或场景已转换为 JSON/glTF/PNG。

## 确认的阻塞：必须补充原始物理容器

- 26 个 FDATA（root RDX 23、system RDX 3），外加 `data/0x25768c1b.file` 共 27 个物理输入缺失。
- 6,118 条 RDB 记录因此没有可读取的原始负载，不能通过算法、哈希名、零填充或重命名来恢复。
- 精确来源、引用记录、平台标志和预计未压缩字节详见 [source_coverage.json](../../UnPack/2.0.1/_reports/source_coverage.json) 与 [missing_input_records.csv](../../UnPack/2.0.1/_reports/missing_input_records.csv)。

## 格式转换仍然待实现

- M3 真实 Magic：4,144 KIDSOBJDB 签名、3,204 G1M、29 G1A，另 82,129 unknown binary。实际导出的资源字节完整，但多数尚无完整结构化解析器。
- 79,714 KT 原生 type_hash 映射涵盖 `.g1s`、`.g1a`、`.g1t`、`.g1m`、`.ktid`、`.kidsobjdb` 等；**仅推断名称的格式不等于已通过内容结构校验**。参考第三方工具 [yumia_fdata_tools](https://github.com/eArmada8/yumia_fdata_tools)，其 README 明确声明未测试其他游戏。
- 本分支工具 `Scripts/unpack/export_native.py` 可以将已发布的 `.bin` / `.partNNNN` 还原为原生扩展名文件，并按原清单 SHA-256 验证，不覆盖原解码产物。详见 [NATIVE_EXPORT.md](NATIVE_EXPORT.md)。
- 原生 `.g1m/.g1t/.kidsobjdb` 文件的重组**不是** glTF/PNG/JSON 等用户可直接阅读格式的语义转换；完整解析、资源关系、模型/贴图/地图渲染与回写仍待独立验证。

## 下一批验收标准

1. 新增物理容器：将合法原始文件放回 `2.0.1/romfs` 精确相对位置，跑 M0、M2、`coverage.py`，直至输入缺失数为 0；如果部分 RDX 对应可选平台不属于当前版本，应给出可追溯的来源依据并重新定义范围，而不是删除记录。
2. 原生格式：按源 RDB/KTID + 内容 Magic 证据，从资源重组推进到结构化 JSON、网格、纹理与材质提取，未知类型保持未支持状态。
3. 验证：完整输出路径、文件存在性、文件大小、SHA-256；涉及渲染需像素/材质/骨骼等真实对照证据。
4. 完整性总结仅可在缺失输入与所有用户要求的转换类别均验收后标记 `FULL_UNPACK_COMPLETE`；当前状态为 **AVAILABLE_SOURCE_BINARY_UNPACK_COMPLETE; FULL_SEMANTIC_UNPACK_BLOCKED**。
