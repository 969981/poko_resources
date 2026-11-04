# Pokopia 2.0.1 — 原始 RomFS 路径镜像解包目录

该目录存放已经实际解码并上传到 `2.0.1_unpack` 分支的逐条资源，**不是**仅供本地使用的占位目录。原始输入保留在仓库 `2.0.1/`，不复制大容器到这里。

**固定路径规则：**

```text
2.0.1/romfs/<relative-dir>/<full-source-filename>
                ↓
UnPack/2.0.1/romfs/<relative-dir>/<full-source-filename>/
    ├── decoded/<record-id>.bin
    ├── decoded/<record-id>.bin.part0001  # 只有超大记录才分段
    ├── raw/<record-id>.bin               # 解码失败/不支持时按需保留
    └── _manifest.csv
```

例如 `LD_C0_R.BIN`、`0x4b13d561.fdata`、`MountPoint_2/0xc884bce7.fdata` 都作为目录名，包含原扩展名。先把 `.7z.001/.002/...` 分卷恢复成 `.fdata`，**不**以分卷后缀建立目录。

`_manifest.csv` 包含原始文件名、源 SHA-256、索引/记录位置、字节大小、解码和发布状态、产物 SHA-256。每轮的状态与统计保存在 `_reports/`。仅对实际成功输出的记录标记 `PUBLISHED`；超过单批体积限制的记录标记 `SKIPPED_BATCH_BUDGET`，不算作完成。

## 自动发布工具

- `Scripts/unpack/publish.py`：LINKDATA 和中小型 FDATA 的索引提取及路径镜像；自动执行原 M1/M2 验证。
- `Scripts/unpack/publish_stream.py`：针对大型 FDATA 的分区、流式解码和大文件分卷输出，不再同时落盘 packed 与 decoded 两套中间文件。
- `.github/workflows/publish-unpack.yml`：LINKDATA 和首批 FDATA。
- `.github/workflows/publish-unpack-phase2.yml`：剩余直接存放的 FDATA、两个小型分卷 FDATA。
- `.github/workflows/publish-unpack-large.yml`：大型分卷 FDATA，按分区提交以控制 Git 推送体积。

原始 `2.0.1/romfs/movie_asset/` 不在处理范围。GitHub 单个文件限制为 100 MiB；常规文件优先直接存储，超过 90 MiB 的已解码资源使用每段 80 MiB 的 `.partNNNN` 文件，需按顺序拼合；超出单批预算的记录由报告列出，待继续处理。

**验收标准：** 仅当 GitHub 分支上真实存在文件、其 `_manifest.csv` 及对应提交记录时，才将其计入已上传；GitHub Actions 运行中或单纯校验成功不等于提交成功。
