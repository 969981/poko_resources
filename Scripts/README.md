# Pokopia 2.0.1 解包工具（M0/M1/M2 首版）

Python 3.10+、仅标准库。默认只读取 `2.0.1/`，所有解析报告写到 `UnPack/` 或 `_meta/`，生成的游戏素材不提交 GitHub。

在仓库根目录运行：

```powershell
# M0：扫描目录和分卷连续性，首次可跳过哈希以快速检查
python -m Scripts.unpack.inventory --source 2.0.1 --output _meta/2.0.1
# 完整校验：耗时和磁盘读取量较大
python -m Scripts.unpack.inventory --source 2.0.1 --output _meta/2.0.1 --hash --test-7z

# 需要先通过现有 .github/workflows/restore.yml 或本地 7-Zip 恢复 .7z.001
# 例如：7z t "2.0.1/romfs/LD_C0_R.BIN.7z.001"
#        7z x "2.0.1/romfs/LD_C0_R.BIN.7z.001" -o_work/2.0.1-restored/romfs

# M1：仅解析索引；这是可在仓库现有 IDX 上直接运行的模式
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --output _meta/2.0.1/linkdata
# 恢复后抽样提取并尝试 zlib；保留 raw，即便解码失败
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --bin _work/2.0.1-restored/romfs/LD_C0_R.BIN --output UnPack/2.0.1/LINKDATA --start 0 --limit 20 --decode --resume

# M2：支持 root+system；若 FDATA 未还原则报告 CONTAINER_NOT_PRESENT
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _meta/2.0.1/ktrdb
# 小样本实际提取；先验证再逐步扩大 limit
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output UnPack/2.0.1/KTRDB --extract --decode --limit 20 --resume

# 验证
python -m unittest discover -s tests -v
```

**状态限制：** M1 的 flag=1 目前会尝试标准 zlib，但必须用真实恢复 BIN 验证；任何解码失败都保留 raw 并记录原因。M2 对 `.file` 仅保留完整原始字节，不宣称对其特殊格式已支持语义解析。大型 FDATA 恢复后再做全量测试，当前已验证的是小型真实 KIDSOBJDB 压缩记录。

## M0–M2 下一轮：真实仓库的自动 smoke 与完整验证模式

- `.github/workflows/unpack-m0-m2.yml`：推送脚本、测试或工作流变更到 `2.0.1_unpack` 自动运行 `smoke`；只 checkout IDX、root/system RDB/RDX、一份真实 FDATA、LINKDATA 两个 7z 分卷以及脚本测试。
- `python -m Scripts.unpack.smoke --source 2.0.1 --output _meta/2.0.1/smoke`：完整索引遍历和 FDATA 真实压缩记录的 byte/hash 验证。
- `python -m Scripts.unpack.linkdata --idx ... --bin ... --output ... --decode --verify-only --limit 250`：解压验证和 hash 报告，**不写出任何游戏素材**。
- `python -m Scripts.unpack.ktrdb --base ... --output ... --extract --decode --verify-only --only-fdata 4b13d561 --limit 250`：有针对性的 FDATA 样本提取验证。
- `python -m Scripts.unpack.full_pipeline --source 2.0.1 --work _work/2.0.1-verify --output _meta/2.0.1/full --sevenzip 7z --verify-only`：完整 7z test/恢复 → 全 LINKDATA 解码验证 → root/system RDB 全遍历与 FDATA 解码验证。计算完整磁盘需求，不够时明确失败，不写出提取游戏素材。

通过 GitHub Actions `workflow_dispatch` 选 `scope=full` 可以手动请求全量；如 GitHub 限制非默认分支手动运行，可在 `2.0.1_unpack` 的脚本变更提交信息中包含 `[full-unpack]` 触发全量分支作业。**请先看 smoke 运行结果及 Runner 可用磁盘空间，不要同时并发多轮全量运行。**

输出状态必须区分 `INDEXED`、`LOCATED`、`EXTRACTED`、`DECOMPRESSED`、`DECODE_FAILED`、`CONTAINER_NOT_PRESENT`。`--verify-only` 只输出元数据、SHA-256 和错误报告；若需实际本地原始二进制导出，使用原 CLI 的 `--extract`/`--decode`（不带 `--verify-only`）。
