---
title: LINKDATA IDX/BIN 字节布局
tags: [pokopia, 2-0-1, linkdata, idx, bin]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---
# LINKDATA：IDX → BIN → 解码内容

**原始索引**：§2.0.1/romfs/LI_C0_R.IDX§；**负载**：§LD_C0_R.BIN§（需要先从分卷恢复）。原始数据不在本手册覆盖范围内，导出写到 §_work/§ 或 §UnPack/§。

## 1. IDX 记录（32 字节，小端）

[源码：core.py / parse_idx](../../../../Scripts/unpack/core.py) 使用 §struct.Struct('<QQQQ')§：

| 相对条目偏移 | 宽度 | 读取含义 |
| --- | ---: | --- |
| §+0x00§ | u64 | §offset§：负载在 BIN 中的字节位置 |
| §+0x08§ | u64 | §unpacked_size§：目标解码长度 |
| §+0x10§ | u64 | §stored_size§：BIN 内保留的原始长度 |
| §+0x18§ | u64 | §flag§：已实现 0 / 1 两种分支 |

索引号是 **零基条目序号**，不是内部游戏 ID。§parse_idx§ 检查文件大小必须为 32 的倍数，并验证相邻条目偏移满足：

§§§text
next.offset == current.offset + ceil(current.stored_size / 256) * 256
§§§

这里的 **256 字节对齐属于 BIN 记录位置**，不要误写成“IDX 的每条宽度 256”。

## 2. 已实现的解码规则

[源码：core.py / decode_linkdata_payload](../../../../Scripts/unpack/core.py)：

- §flag=0§：§stored§ 必须等于 §unpacked§，直接返回原始 bytes。
- §flag=1§：优先识别分块头：小端 §u32 chunk_size, u32 chunk_count, u32 unpacked_size§，其后 §chunk_count§ 个 §u32 stored_extent§；头长度按 §0x80§ 向上对齐。
- 每个常规块的存储起点先读 §u32 packed_size§，再严格检查单个完整 zlib stream；向下一块推进时，当前 extent 按 §0x80§ 对齐。
- 解码器允许带约束的特例：0 字节占位头，及少数 ≤32 字节的短原样末块；未命中已知分块头时尝试完整单段 zlib，不扫描任意 zlib 特征字节。
- §flag§ 超出支持范围 / 长度不匹配立即报错，不写“已成功解码”。

## 3. 只读分析与少量导出

§§§powershell
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --output _meta/2.0.1/linkdata
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --bin _work/2.0.1-restored/romfs/LD_C0_R.BIN --output _work/link-sample --start 4645 --limit 9 --decode --resume
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --bin _work/2.0.1-restored/romfs/LD_C0_R.BIN --output _meta/link-verify --decode --verify-only --limit 250
§§§

§raw/NNNNN.bin§ 与 §decoded/NNNNN.bin§ 是不同层次的证据。§--verify-only§ **不导出 payload**，仅报告状态与哈希；转换文本应从真实 decoded 文件开始。九语言样例 §04645§～§04653§ 见 [[06-Native-Text-Tables]]。

## 4. 最小验收和排错

必须记录：原始 IDX/BIN 的 SHA-256、记录号、四个原始字段、raw SHA、decoded SHA、成功或错误代码。典型错误：§IDX_SIZE_NOT_MULTIPLE_OF_32§、§IDX_OFFSET_ALIGNMENT_MISMATCH§、§LINK_CHUNK_BOUNDS§、§LINK_TOTAL_UNPACKED_SIZE_MISMATCH§。仅 §INDEXED§ 不代表从 BIN 提取完成。

相关：[[../Workflows/01-Restore-And-Decode]]、[[../README|技术首页]]。
