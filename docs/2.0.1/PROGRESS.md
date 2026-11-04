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
