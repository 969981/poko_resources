# M0–M2 第二轮：自动化可执行验证

- 分支：`2.0.1_unpack`
- 目标：真实文件验证，不修改 `2.0.1/` 或 `main`。
- 本次新增：`Scripts/unpack/smoke.py`、`Scripts/unpack/full_pipeline.py`、`--verify-only`、`--only-fdata`、GitHub Actions smoke/full 工作流、对应测试。
- 本地（模型执行环境）已通过 **10 项** Python 单元测试，包括两项 `--verify-only` 资产不落盘回归测试。
- **Actions 是否真正成功、LINKDATA 实体 BIN 内容的压缩类型、全部 RDB 记录提取率，以后续对应 run 的报告为准；没有运行证据前不填写成功百分比。**

## 自动 smoke（push）

1. 仅 sparse-checkout 关键索引与两个 LINKDATA 7z 分卷、小型 FDATA、脚本和测试；使用 `filter: blob:none` 降低资源占用。
2. 跑 10 项单元测试。
3. 实际遍历 `LI_C0_R.IDX` 及 root/system RDB/RDX；比对真实 FDATA 第 2 个 KIDSOBJDB 记录的解压数据。
4. `M0` 对已选择的资源进行 SHA256 和 7z test；**不是全部 99 个资源文件的完整校验**。
5. 恢复 `LD_C0_R.BIN` 到 Runner 临时目录，对前 250 条非空 IDX 项目做压缩尝试，并将未知/失败作为明确状态记录。
6. 用真实 RDB 索引和 `0x4b13d561.fdata` 做目标样本抽检；未 checkout 的容器一律不算资源缺失。
7. 仅上传 JSON/CSV/日志元数据 Artifact；不上传游戏二进制和解压输出。

## 完整模式（workflow_dispatch/full 或显式 `[full-unpack]` push）

1. 下载全部 GitHub 已追踪的 `2.0.1/` 资源（保留 exefs/main，movie_asset 排除）。
2. 计算每组分卷目标大小与峰值空间。要求额外空余 1 GiB；若不满足，**如实失败并指出所需空间**，建议使用自托管 Runner 或本地 7z。
3. `M0` 全目录 SHA256 清单，全部卷号完整性、`7z t` 和恢复输出字节数验证；恢复的临时文件位于 `_work/` 或 Runner temp。
4. `M1` 逐条验证 12,298 个 IDX 索引与恢复的 BIN，计算 raw/decoded SHA256、状态和错误分类，完成后删除临时 BIN 以节省空间。
5. `M2` 恢复 KT RDB/FDATA `.file` 容器，遍历 root/system 全部索引并按项验证；未知格式及缺少容器单独记录。
6. 不重新提交提取出的游戏内容，只保留运行报告。对 `FAILED/UNSUPPORTED` 类型优先修复编码器，而不是改写原始数据。

## 验收标志

- **代码已提交** ≠ **GitHub Actions 已执行** ≠ **全部解包成功**。
- `smoke` 成功只说明小样本验证通过。`full` 需要单独的运行记录、每阶段 CSV/JSON 报告及分子/分母；不能根据历史离线索引审计数据虚构成功率。
- 若 GitHub App 凭证无法写 `.github/workflows/`，需使用具有 workflow 写入权限的 GitHub 凭据；其余脚本和文档仍可合并。
