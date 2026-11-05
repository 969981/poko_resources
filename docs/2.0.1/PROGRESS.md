# 解包进度日志（仅记录已验证事实）

## 2026-11-04 — M0/M1/M2 首轮实施

- 仓库：`969981/poko_resources`；分支：`2.0.1_unpack`；计划基线提交：`242781c9ff2546d5b848a016bfb60f7a4c70cdc3`。
- **M0 目录清点**：实际 GitHub 目录共 99 文件，压缩分卷 10 组 / 70 件，目录编号检查 0 处断号；完成仅是远端目录列表层面的检查。未全量下载，尚未执行每件 SHA-256、`7z t` 或所有资源恢复。
- **M1 IDX 结构实测**：393536 字节，12298 条，每条 32 字节，flag=0 有 4169 条、flag=1 有 8129 条、stored_size=0 有 2505 条，256 字节对齐偏移连续；尚未得到解压后的 `LD_C0_R.BIN`，**提取/解码率未验证**。
- **M2 RDX 结构实测**：`root.rdx` 45 条、`system.rdx` 5 条；`0x4b13d561.fdata` 真实样本首部是 `PDRK0000`，记录始于 0x10；第 2 条 KIDSOBJDB 解压前 88 字节、解压后 96 字节，真实分块 zlib 试验通过。远程 RDB 大文件本轮未能完整读入，RDB 内容需在 GitHub Runner/本地实测。
- 新增 M0 盘点脚本、M1 IDX/提取脚本、M2 root/system RDB/FDATA 提取脚本、真实压缩片段与合成 fixture 混合测试；执行 `python -m unittest discover -s tests -v`：**8 项通过**。

## 当前未完成的验收

1. **M0**：所有源文件 SHA-256、整套 7z `test`、恢复输出大小与哈希核验。
2. **M1**：从实际恢复后的 BIN 提取并逐项解码。`flag=1` 是否标准 zlib 必须用真实样本确认。
3. **M2**：解析真实 `root.rdb/system.rdb`，按 50 个 RDX 索引及特殊 `.file` 查缺，完成真实 FDATA 批量提取与可重复报表。
4. 不能因 8 项单元测试通过，宣称全量资源解包完成。

## 下一次验证命令

详见 `Scripts/README.md`。先执行：

```bash
python -m Scripts.unpack.inventory --source 2.0.1 --output _meta/2.0.1 --hash --test-7z
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --output _meta/2.0.1/linkdata
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _meta/2.0.1/ktrdb
python -m unittest discover -s tests -v
```

在 `_work/2.0.1-restored/` 解压完成后，再使用 `--bin`、`--extract --decode` 以有限 `--limit` 做真实样本提取并保存完整状态报告。

## M0–M2 第二轮验证（2026-11-04）

- [完整实测报告](./ROUND2_RESULTS.md) 已记录真实 Actions 运行与恢复测试。
- M1：12,298 IDX 记录全部分类；9,792 数据解码成功，1 条有效零长度占位，2,505 空索引，0 失败。对应 Run #41824089583。
- M2：root 60,722 + system 25,110 = 85,832 条 RDB 索引可解析；单个小型 FDATA 520/520 条成功解压，5,219 扩展 footer 尚待解读。
- M0：LINKDATA 两卷已通过 7z t/恢复；其余分卷的完整校验仍待全量 run 结果。
- 额外已触发 [全量尝试 Run #41824295903](https://github.com/969981/poko_resources/actions/runs/41824295903)，状态以 Actions 日志为准。

## 第三轮全量结论（2026-11-04）

- [Run #41825954077](https://github.com/969981/poko_resources/actions/runs/41825954077) **smoke/full jobs 均通过**，使用真实仓库原始资源，恢复并核对 10 组 7z 分卷；99 个输入文件完成 SHA-256 清单。
- M1 LINKDATA：12,298/12,298 成功解码或空记录分类，其中 9,792 解码、1 个零长度占位、2,505 空记录，0 失败。
- M2 RDB：root 60,722 + system 25,110；**79,710 条 FDATA 解压成功**，**4 条独立 FILE 原始负载流式校验成功**，实际提取/解码失败 0。
- 5,219 条 system 17 字节 footer 已经通过真实 `0x38f972af.fdata` 回读并成功解码；26 个未提供实体 FDATA 仍对应 6,118 条未定位记录（其中额外含 1 个独立 FILE 未提供）。
- 结果只包含元数据和 SHA-256，完整资源仍在 Runner 临时目录中，不将原版游戏素材作为 Git 提交。
- 详情见 [ROUND3_RESULTS.md](./ROUND3_RESULTS.md) 和 [MISSING_CONTAINERS.csv](./MISSING_CONTAINERS.csv)。下一阶段 M3 应对 KIDSOBJDB 和 schema 做结构化解析与验证。

## M3 SQLite 关系索引验收（2026-11-04）

- [Run #41856591033](https://github.com/969981/poko_resources/actions/runs/41856591033) **成功**。工作流 `unpack-m3-sqlite.yml` 复用已发布 M3 类型索引、8 份 M4 KIDSOBJDB 结构证据、原始 RDB/RDX/IDX 和原始缺失资源清单，执行 SQLite 严格数量/来源/SHA 关联、integrity_check 与外键检查。
- **89,507** 条已发布资源、**98,130** 条原始 IDX/RDB 定位记录、**6,118** 条缺少实体的资源、**4,144** 条 KIDSOBJDB 对象记录、**626,349** 个 IDOK/RDOK 数据块、**8,112,762** 条字段元数据全部入库。
- **271,271** 条 U32 数值与资源名称 Hash 相等的**未验证候选**独立存表，不能计为已恢复真实引用链。
- SQLite 大小 **1,159,593,984** 字节；CSV/JSONL/SQLite 压缩包存于 [Actions Artifact #13337139016](https://github.com/969981/poko_resources/actions/runs/41856591033/artifacts/13337139016)，30 天保留。Git 只留 `UnPack/2.0.1/_reports/m3_sqlite_summary.json` 和工具，不提交大体积数据库。
- 查询文档：[M3_SQLITE.md](M3_SQLITE.md)，源码：[m3_database.py](../../Scripts/unpack/m3_database.py)。
- **尚未完成**：BFBS schema 的实际身份/路径证明（当前前缀扫描确认 0 条）、属性 Hash 的可信文本名称映射、RDOK 语义、真正对象引用及 `MissionSettings` 资源→PE 工厂→Lua handle 同一来源的证据链。M3 数据库完成不等于语义解析全部完成。

## M3 RDOK 静态证据推进（2026-11-04）

- 读取已提交的、SHA-256 验证过的 15 份 KIDSOBJDB 诊断记录，提取其中**全部 40 个 RDOK**，与 4,144 条 KIDSOBJDB 原始资源名称 Hash 对账：**40/40 唯一对应，0 歧义**。
- 所有目标都有 IDOK，40 条同 root/system 分区、32 条同 FDATA、8 条跨 FDATA；记录源/目标原始路径和 SHA-256。见 [RDOK 证据表](../../UnPack/2.0.1/_reports/m3_rdok_verified_40.csv) 和 [分析文档](M3_RDOK_DIRECT_EVIDENCE.md)。
- 外部 DWOriginsAssetTool 的 RDOK `object_hash / parent_database_hash / parent_object_hash / property_count` 布局与本次 40 条实际字节吻合，定位为 **强静态支持、运行时语义未证明**。
- 已提交 `m3_rdok_crosswalk.py` (字段 Hash 频率与 ExeFS 字符串只读扫描)、`m3_rdok_sqlite.py` (候选关联导入 SQLite 的 SHA/IDOK/路径/原始字节验证)，相关 GitHub Actions 处于排队状态时不得称测试通过。
- 重要更正：旧研究中 `MissionSettings_array.bfbs` / `MissionInfo_array.bfbs` 来自 **SV DLC** 的 pkNX 资源路径，不能当作 Pokopia 真实资源名；仅保留静态负例检索。Pokopia 自己的 BFBS schema、字段 Hash 文本与运行时加载关系仍未完成确认。

## M25–M26 原生村民图标与 KIDS 双数组（2026-11-05）

- M25：原始 KIDSOBJDB 678/678 数据库逐字节扫描，找到一个 3,543 元素的原生图标源对象字段，分出 314 常规 + 314 uni 图标槽位；从已归档原始 TEXINFO 解码 `.bin` 和原始 G1T 实际补出 26 PNG，其中 17 张与此前缺失参考肖像达到独立高置信视觉对应。原生村民候选覆盖更新为 **307/378**；原始 `Villagers/Native_2.0.1/Icons/` 现有 307 张实体 PNG。
- M26：对剩余 62 张 PokoHex 肖像编号 `317–378` 与全套 **629 原生 Source OID / 635 张 SHA 校验的 PNG** 重新比对，**0 个新增可靠匹配**。9 张多候选得到了各组最优互斥视觉推荐，但**尚未证明运行时游戏 ID**。
- M26.2–M26.3：原始 NSO0 已确认 BSS 类 `main+0x367AD40`、类型方法表 `main+0x33135C8`、属性枚举函数 `main+0xDD1B48`，并直接从原生 rodata 三项属性描述器返回 `0x2F610FEA`、`0xE88C8D60`、`0x34CBB458`。
- M26.4：从原始 KIDSOBJDB 恢复 **3,543 对连续原生 u32**；前一个字段 `0xE88C8D60` 的值全部唯一且不等于 0，后一个字段 `0x34CBB458` 有 628 个条目可逐项关联到已确认 Source OID。常见名称 Hash 假设试验没有命中。尚缺真正的**运行时物种/村民 ID → 原生键或数组索引 → Source OID** 读取调用链。
- M23 的两个 FF03 容器 `0x03a38715.fdata` 和 `0xfd6af828.fdata` 仍未获取原始负载；M25 已恢复的 26 张 PNG 源自**已有** `0x00011c54.fdata`，不可误记为 FF03 已恢复。

详见 [[M26_VILLAGER_ROSTER_AND_KIDS_PARALLEL_ARRAYS]] 和 [[M25_NATIVE_POKEMON_ICON_REGISTRY]]。所有结果由 2.0.1 原生字节和 Actions 独立验证，未写入未经证明的游戏正式身份映射。

## M27 — KIDS 图标数组 31 多项式与四位数字逆序拟合（2026-11-05）

- 直接用原始 `root_019167_50ae86ef.kidsobjdb`（SHA-256 钉住）校验 3,543 对 u32，以及 M25 的 628 个 Source OID。
- 找到以 `31` 为乘数的四位数字 **逆序字符串**公式：常规图标 key/OID 指数 `11/66`，uni 图标 `15/70`，每形态有独立的常数项。样例 `0043→3400`，原生 slot455 key=`0x469E2C00`、Source OID=`0x06AB845F`。
- 总计 **626 条**有 4 位数字的图标满足模型，其中独立留出样本 **612/612 同时匹配 key 和 OID**，14 组中的 4 组为单样本未独立验证。非数字的 `icon_poke_blank` 与 `icon_poke_uni_hatena` 保留原始字段。
- 枚举 14 组 × `0000–9999` = 140,000 个候选，从原始 3,543 项双数组中得到 **626 条键和值同时一致**、新图标对象 0 条；这并不能证明游戏完全没有其它来源或版本图像。
- M27 只完成**数学模型与原始字节对账**，尚未证明 NSO 中真实 Hash 实现、字符串来源或游戏物种 ID 消费者；307/9/62 状态保持不变。参见 [[M27_ORIGINAL_KIDS_REVERSE31_NUMERIC_HASH]]。
