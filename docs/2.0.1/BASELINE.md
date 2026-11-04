# Pokopia v2.0.1 源资源与索引基线

## 当前 GitHub 仓库已核对（2026-11-04）

- 仓库：`969981/poko_resources`；默认分支 `main`
- 基础提交：`e77afe020de790c84563638020e77925f0e698c4`
- 原始输入：`2.0.1/exefs/{main,main.npdm,rtld,sdk,subsdk0}`
- LINKDATA：`2.0.1/romfs/LI_C0_R.IDX`，`LD_C0_R.BIN.7z.001`、`LD_C0_R.BIN.7z.002`
- KT：`2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/` 含 `root.rdb`、`root.rdx`、`system.rdb`、`system.rdx`、若干 `*.fdata` / `*.fdata.7z.NNN`、`MountPoint_1`、`MountPoint_2`、`data/`
- `.github/workflows/restore.yml` 已提供手动运行的 7-Zip 分卷恢复与空间评估流程，**不应因开新分支再复制一个自动运行的高成本工作流**
- `romfs/movie_asset/` 已按既有打包策略排除；`exefs/main` 必须保留

以上是 GitHub 目录/文件名层面核实，**尚未对分卷执行真实下载/解压/内容哈希验证**。

## 先前离线索引审计（待用仓库实物重验）

此前独立上传的 `pokopia_201_inventory.csv` / RDB/RDX/IDX 的只读审计观察到：

| 项目 | 历史审计值 | 解读 |
|---|---:|---|
| `root.rdb` 记录 | 60,722 | 仅 root、不是 root+system |
| 映射至当时实体 FDATA 的 root 记录 | 54,656 | 仅定位，不代表可提取 |
| 当时未定位实体 FDATA 的 root 记录 | 6,066 | 需要验证 system/RDX/分区 |
| `root.rdx` FDATA 映射数 | 45 | 22 项与当时文件清单匹配 |
| KIDSOBJDB 索引记录 | 4,479 | 4,108 项当时关联实体 FDATA |
| 未在 root.rdx 发现的实体 FDATA 名称 | 0x38f972af、0x52482d03 | 待查 system.rdx，不能擅自推测 |

这组数不是本 GitHub 最新解包报告，不能把缺少路径直接写成“游戏文件缺失”；新工具完成 M0/M2 后应覆盖此表并记录数据来源与 SHA-256。

## 样本突破路径

- `b290631c.kidsobjdb` → `0xe634eeb2.fdata`；历史候选 offset=0x10、长度=697906
- `cfd2bd1f.kidsobjdb` → `0xacd220a8.fdata`；历史候选 offset=0x24fd60、长度=77600
- `d14d76ef.kidsobjdb` → `0x2943e4da.fdata`；历史候选 offset=0xd78920、长度=2381972

必须重新比对对应仓库实体文件、索引含义与真实数据头才能宣布提取成功。

## 覆盖率定义

- index_rate = 解析成功的索引记录 / 索引总记录
- location_rate = 有验证容器路径的记录 / 索引总记录
- extraction_rate = 原始字节已成功提取的记录 / 索引总记录
- decompression_rate = 完整解压并验证的记录 / 需要解压的记录
- semantic_rate = 有结构验证的记录 / 候选可解析记录

任何阶段都同时给出分子/分母和 unsupported/unknown/failed 分类。
