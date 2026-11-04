# Pokopia 2.0.1 全资源解包计划

## 0. 目标、范围和不做的事

**最终目标**：把游戏版本 2.0.1 的已有资源从容器恢复为可检索的目录，建立无损证据链，继续导出数据库、贴图、模型和场景，最后把地图/洞窟/建筑内部渲染成可验证的素材。所有转换均需要有原始记录可回查，优先保留 raw。

**输入**：本仓库 `2.0.1/exefs/` 与 `2.0.1/romfs/`；`romfs/movie_asset/` 不在本次输入范围，`exefs/main` 在范围内。源文件可能以 `*.7z.001` 等多卷形式存在。**不修改输入、不上传新增的游戏资源数据。**

**约定**：解析完整 ≠ 解压成功 ≠ 语义理解。未验证的格式标记 `UNKNOWN`，不得以扩展名猜测成功。

## 1. 解包架构

```text
2.0.1 (read-only)
   │ inventory / SHA-256 / 7z volume check
   ▼
M0 Manifest + _meta/2.0.1/inventory.csv
   │ restore only to disposable workspace
   ├───── LINKDATA: IDX -> record -> BIN offsets -> raw -> codec -> decoded
   └───── KT: RDB -> RDX -> FDATA / standalone .file -> raw -> codec -> decoded
                          │
                          ▼
               type signatures + provenance + sample tests
                          │
                KIDSOBJDB / BFBS / tables
                          │
                 JSON / CSV / SQLite
                          │
                texture / model / scene / map
```

## 2. M0 源文件盘点与还原 [P0]

1. 从 GitHub 分支枚举源文件、大小及分卷名称；生成 manifest；记录 Git commit 和工具版本。
2. 检查每组 `*.7z.001..` 编号连续，先运行 `7z t`，再恢复到 `_work/2.0.1-restored`；恢复后对大小、CRC/哈希、路径做检查。
3. 重用现有 `.github/workflows/restore.yml` 的手动还原逻辑；避免在 PR/每次 push 自动触发 6GB+ 工作。
4. 先小样本，后全量。磁盘不足时失败并明确提示，不要覆盖或删除原始 Git 内容。
5. 清单输出 `_meta/2.0.1/{inventory.csv,volumes.csv,restore_report.json}`；记录成功、缺卷、解压失败、路径冲突。

**验收**：输入文件一一枚举，分卷状态可追溯，恢复路径不越界。未跑真实还原不能在进度中记为完成。

## 3. M1 LINKDATA [P0]

1. 对 `LI_C0_R.IDX` 按实际文件头/字段恢复索引版本、数量、记录宽度、endian、位域含义；记录原始字段。
2. 用 `LD_C0_R.BIN` 的真实解包结果核验 offset、packed-size、unpacked-size；确保所有记录边界不越界。
3. 实现流式读取与 raw 资源提取，文件命名采用确定性 ID/Hash，不把未知记录捏造为 PNG/文本等。
4. 分开识别 raw、zlib、可能的 Oodle/其他算法；提供 codec 选择与失败报告；不根据头两个字节就断言所有数据可解压。
5. 进行 10 个以上不同类型样本提取、前后哈希/结构检测；覆盖低 ID、高 ID、空项、重复项、压缩项。
6. 完整遍历索引，导出每条记录状态：`INDEXED/LOCATED/EXTRACTED/DECOMPRESSED/DECODED/FAILED` 与失败原因。

**验收**：`linkdata_entries.csv` 行数对应实测 IDX 条目；条目状态无静默丢失；抽检逐字节可重现。

## 4. M2 KT RDB / FDATA / FILE [P0]

1. 分别解析 root 与 system 两套 RDB/RDX，不能只遍历 root。
2. 还原 RDB record -> RDX FDATA index/hash -> `KIDS_PLATFORM_OUNCE/`、`MountPoint_1`、`MountPoint_2` 等容器定位；对未知标记保留原始 flags。
3. 为特殊 `*.file` 记录使用独立的容器定位逻辑，不能强套 FDATA offset。
4. 每条记录进行合法性检查：文件存在、offset+size<=容器大小、压缩标记/数据头与解压结果一致。
5. 优先跑已知 KIDSOBJDB 三个样本；不同大小/分区再选代表样本。
6. 导出 `rdb_records.csv`、`rdx_containers.csv`、`unresolved.csv`，区分 `not_present`、`unsupported_flag`、`out_of_range`、`decode_failure` 等。

**验收**：root/system 索引按实测数量对齐，每条记录都有可追踪的定位结果或原因码；实体定位率不能冒充提取成功率。

## 5. M3 结构数据 [P1]

1. 根据 signature/结构而不是后缀分类；保留原始二进制、头 64 字节及 source mapping。
2. 解析 KIDSOBJDB 的 header、对象表、成员、引用、字符串和多语言字段；针对无法确定的字段保留 raw bytes。
3. 检测 BFBS/FlatBuffers schema 与内存结构、Lua/ExeFS 字符串的交叉引用，按证据逐条确认。
4. 导出一致的 `resource_catalog.sqlite`、CSV、JSON；建立 `record_id -> source_path + offset -> converted_path`。
5. 挑战样本：`MissionSettings` 等具体资源必须验证实际行名/路径/工厂类型；不要仅凭名称匹配下结论。

**验收**：字段可逆回查，样本有测试，语义无法证明就标 `unknown`。

## 6. M4 模型/贴图/地图 [P1/P2]

1. 分类资源 signature 与容器类型，挑出模型/贴图/材质/场景候选。
2. 验证格式和坐标系，再转换 GLB、PNG、JSON，不可用文件命名代替格式验证。
3. 还原引用关系、地形/建筑/道具摆放、场景网格、场景矩阵、材质和贴图绑定。
4. 将室外、建筑内部、洞窟和地下世界 **分别** 重建，不把独立矩阵拼成伪完整地图。
5. 生成分块渲染；处理裁剪黑块、边界拼缝、贴图错配，并留对照图及 source ID。

**验收**：每个成功场景都有对应原始资源列表、可重现的渲染配置及实际对照；未知资源/场景单列。

## 7. M5 自动化、质量与发布 [贯穿各阶段]

- 支持 `--dry-run`、`--limit`、`--resume`、`--force` 和输出根目录。
- 清单型 SQLite 保存 pipeline version、输入哈希、阶段状态、错误、输出哈希和处理耗时。
- 失败可重试，不删除成功输出；重复运行输出一致。
- GitHub Actions 只做快速索引/小型 fixture 的 CI；大规模 7z 恢复与格式转换使用本地或空间足够的自托管 Runner。
- GitHub 只存工具代码、测试、文档、可发布的小型非游戏原始元数据；禁止上传额外整套受保护资源和大量转换资产。
- 阶段完成必须更新 PROGRESS 和测试证据，给出总量、成功数、失败数、未知数以及失败原因分布。

## 8. 里程碑停止条件

- **M0**：manifest 与分卷校验覆盖全部输入文件
- **M1**：IDX 全记录均有状态和可追溯的索引/解包输出
- **M2**：root+system 索引遍历完整，未定位与错误明确归类
- **M3**：至少一类真实结构对象成功导出、反查与测试
- **M4**：至少一个真实场景可复现渲染，洞窟与内部单独跟踪
- **M5**：CI 通过，增量重跑一致，错误报告完整

目标是完整并可验证地处理输入范围内的所有资源；对于暂不支持的特殊压缩格式，需保留原始数据和明确的问题记录，不伪造 100%。
