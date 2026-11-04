# M0–M2 第二轮实测报告（2026-11-04）
 
## 结论

**M1 LINKDATA 已完整遍历并验证所有记录的字节级解码；M2 仅完成小型实际 FDATA 的全部 520 条样本，M0 全输入验证仍未完成。** 不将 INDEXED/LOCATED 计算为 EXTRACTED/DECOMPRESSED。

### GitHub Actions 实证

- [Run #41824089583](https://github.com/969981/poko_resources/actions/runs/41824089583)：success，Python 单元测试 14 项通过。LINKDATA 7z 通过真实 `7z t`，BIN 还原为 **247,317,504** 字节。
- LINKDATA `LI_C0_R.IDX` 完整 **12,298** 条：非空数据 **9,792** 成功解码、**1** 条有效零长度占位头、**2,505** 条空索引，**0** 条解码失败。
- 解码记录使用 0x80 对齐分块头（可变 64/128/512 KiB 分块）、u32 packed-length zlib 和受限的短原始尾块。所有生成的 hash/状态存于该 Run 的 Artifacts；没有上传 decoded 游戏资源。
- RDB：root **60,722**、system **25,110**，共 **85,832** 条完整可解析索引。RDX root 45、system 5；共 50 条。
- 小型 `0x4b13d561.fdata` 的 **520** 条可定位记录完成真实解压验证（520 成功，0 失败）。这不代表其他 23 个现存 FDATA 容器的解包结果。
- system RDB 中 **5,219** 条 17-byte footer（`0x0401`，额外字段含 `0x80000000`）目前仅原样存储，未得到独立实体容器与偏移的最终验证。不能把它标记为已经映射。
- 在 sparse checkout 的 M2 run 中，**80,093** 条显示 `CONTAINER_NOT_PRESENT` 是因为样本 Runner 没有下载其他 FDATA，并非真实缺失游戏文件，不得用作完整性失败数。

### M0 范围

- GitHub 文件清单 99 个路径，10 组/70 个分卷；仅在目录层面验证卷号连续。
- 实际解压测试覆盖 LINKDATA 1 组 2 卷，未全量执行所有分卷的 7z t 和哈希。
- [Run #41824295903](https://github.com/969981/poko_resources/actions/runs/41824295903) 已请求全量 `[full-unpack]` 执行：结果需要以该 run 自身完整日志/Artifact 为准，不能提前宣布成功。

### 验收下一步

1. 查看 full run 的磁盘预检；容量不够则改在自托管 Runner 或按独立 FDATA 容器分批恢复。
2. 对 24 个 GitHub 已存在 FDATA 容器逐个验证 IDRK 位置、packed/unpacked、hash，处理 `.file` 特殊记录。
3. 对 17-byte system footer 先验证 `<HIIIHB>` 候选字段解释，必须与大 FDATA 的真实 IDRK header 对账后才能确认语义。
4. 保存每条 record 的 source SHA、offset、size、flags、raw/decoded SHA 与错误分类；再进入 M3。

## 关键文件

- `Scripts/unpack/{inventory,linkdata,ktrdb,smoke,full_pipeline,core}.py`
- `.github/workflows/unpack-m0-m2.yml`
- `tests/test_unpack_core.py`
- `docs/2.0.1/ROUND2.md`
