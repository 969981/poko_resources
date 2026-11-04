# Pokopia 2.0.1 完全解包状态与事实边界

目标分支：`2.0.1_unpack`。必须区分以下不同验收含义：

- **M0 原始输入校验**：原始文件与分卷完整性；历史 Actions `#41825954077`。
- **M1/M2 字节级解包**：LINKDATA、RDB/FDATA/FILE 的负载已提取、流式解码并按原始路径归档。源容器提取不等于语义资源转换。
- **提交及大小验证**：`manifest_reconciliation.json` 已验证 89,507 条、18,375,770,432 字节，Git 文件存在性/大小检查 0 异常（Actions `#41837368221`），并未重新下载所有资源计算 SHA-256。
- **M2 原始源文件覆盖校验**：`Scripts/unpack/coverage.py` 对照真实 IDX/RDB/RDX、Git HEAD 文件树和发布清单，输出 `source_coverage.json`、`missing_input_records.csv` 和 `unpublished_records.csv`。
- **M3+ 语义转换**：KIDSOBJDB、BFBS、贴图、模型、材质、地图等需要实际格式验证；单纯 `.bin` 不代表这些阶段完成。

## 不可被算法忽略的原始输入缺口

`root.rdb` 与 `system.rdb` 合计 85,832 条。此前全量实测确认 79,710 条 FDATA 解码和 4 条独立 FILE 原始负载，尚有 **6,118 条因缺少实体源文件无法提取**。

`docs/2.0.1/MISSING_CONTAINERS.csv` 记录缺少的 26 个 FDATA（root.rdx 23 个、system.rdx 3 个）；RDB 另引用未提供的 `0x25768c1b.file`。当前源目录无法通过修改解压算法恢复这些缺失字节，亦不能凭索引中的 hash 伪造素材。

新增 `source_coverage.json` 作为最新逐条实证对账依据；若原始实体存在但未发布，则覆盖门禁立即失败，不能称为 100%。

## 待完成

1. 获取缺失的合法原始 FDATA/FILE 输入，保持原 `2.0.1/romfs` 相对路径，验证哈希后补提并复核。
2. 对已提取负载生成 M3 类型签名清单，保留源哈希、RDB ID、输出路径、Magic、置信度；未知格式保持 UNKNOWN。
3. 对实测支持的格式进行结构化转换、校验及（需要时）可视化；避免根据猜测修改扩展名。
4. 只有源输入覆盖与所需资源格式转换全部验收后，才宣布完全解包。
