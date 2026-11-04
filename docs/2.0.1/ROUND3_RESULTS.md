# Round 3 — M0/M1/M2 完整验证结果（2026-11-04）

> Provenance: [GitHub Actions Run #41825954077](https://github.com/969981/poko_resources/actions/runs/41825954077), commit `c4dc83b4929cc6969b6f456459d2e74ee0a44954`. Only index/hashes/reports were exported as an Action artifact; restored game payloads stayed on the Runner.

## 本轮结果

| 指标 | 数量 | 证据 |
|---|---:|---|
| GitHub 输入文件 | 99 | `m0/inventory.csv` 全部计算 SHA-256 |
| 7z 分卷组 | 10 | LINKDATA 1 组 + KT 9 组，都通过 7z t 与恢复大小检查 |
| LINKDATA IDX 记录 | 12,298 | 9,792 个解码成功、1 个零长度占位、2,505 空记录、0 失败 |
| RDX 索引 | 50 | root=45、system=5 |
| root RDB 索引 | 60,722 | 全部成功解析 |
| system RDB 索引 | 25,110 | 全部成功解析 |
| FDATA 数据解压 | **79,710** | IDRK header、name/type、存储长度、解压长度和输出 SHA-256 验证 |
| 独立 `.file` 原始负载验证 | **4** | 读取 56-byte IDRK+metadata、流式 SHA-256；不复制大文件进入 Python 内存 |
| 未提供对应物理容器的记录 | **6,118** | 已分类为 CONTAINER_NOT_PRESENT，不是解码失败 |
| 实际验证失败 | **0** | 不存在 EXTRACTION_FAILED / DECODE_FAILED |

**可用记录验证率：79,714 / 79,714 = 100%；按全部 RDB 记录计算：79,714 / 85,832 = 92.8721%。**

## 17 字节 system RDB 扩展 footer

- 之前 opaque 的 **5,219 条** 已全部证实为 `<HIIIHB>` 格式：magic=0x0401, marker=0x80000000, offset, stored_size, RDX index=0, final byte=0。
- 关联 `system.rdx[0] -> 0x38f972af.fdata`，5,218 个相邻偏移严格连续，最后记录结束位置与文件实际长度 **2,560,389,883 字节**精确一致。
- **5,219 / 5,219** 成功从大 FDATA 中按 offset 回读 IDRK 原生头部，校验 name/type hash、entry size、unpacked size 并完成解码。没有留下 opaque_17 记录。

## 独立 FILE（4 条全部流式验证成功）

| 源文件名（.file） | 记录索引 | 原始负载大小（字节） | 解码结果 |
|---|---:|---:|---|
| `0x0b5db05b.file` | 2783 | 246875856 | RAW_VERIFIED |
| `0x272c6efb.file` | 9421 | 946606880 | RAW_VERIFIED |
| `0x9d464c3c.file` | 37314 | 50781664 | RAW_VERIFIED |
| `0xf71746ba.file` | 58558 | 176809152 | RAW_VERIFIED |

- 存储文件比 raw 负载恰好多 56 字节（IDRK 48B + metadata 8B）。
- 原始负载未压缩，按 chunk 流式哈希与 IDRK 声明长度吻合；不将字节级验证说成语义解析。

## 输入缺失项

- `root.rdx` 中 23 个 FDATA 缺实体，`system.rdx` 中 3 个 FDATA 缺实体，总共 **26 个缺失容器**；详见 `MISSING_CONTAINERS.csv`。
- 此外 `0x25768c1b.file` 在 RDB 中有引用但不在本仓库提供的文件列表中（不计入 RDX FDATA 26 个）。
- 6,118 条未定位的记录不会被虚报为校验通过；可用剩余安装分区/版本资源进行后续对账。是否属于可选安装区或未上传内容仍需证据。

## 交付与下一阶段

- 解包脚本：`Scripts/unpack/core.py`, `ktrdb.py`, `linkdata.py`, `full_pipeline.py`。
- 最终结果：运行页面下 `pokopia-m0-m2-full-41825954077` artifact（CSV/JSON 索引与报告，无游戏负载）。
- 源文件保持只读，`2.0.1/exefs/main` 保留；没有再次向 GitHub 上传解码后的游戏素材。
- **下一阶段 M3：** KIDSOBJDB / FlatBuffers 类型判定、字段与资源名关联、可回溯 SQLite/JSON/CSV。需以真实样本验证结构，不能只依据 Hash 或文件后缀。
