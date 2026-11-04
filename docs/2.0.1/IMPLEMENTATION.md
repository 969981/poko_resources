# M0–M2 第一轮实现 / 真实样本观察

## 仓库文件清单快速核验（GitHub 目录接口）

- 逐级列出 `2.0.1/exefs/`、`romfs/`、KT 根目录及 3 个子目录；共 99 个文件（包含分卷），总存储字节数 6,563,012,216。
- 已发现 10 组 7z 分卷、70 个分卷文件；逐组编号从 001 开始无间断。**此为目录连续性校验，并非下载、7z t 或 SHA-256 校验。**
- 直接存放的文件还有 18 个 FDATA、2 个 RDB、2 个 RDX、1 个 `.file`、1 个 IDX 及 ExeFS。

## 已知文件格式证据（2026-11-04）

使用 GitHub 连接读取 `969981/poko_resources` 分支中的实际二进制文件，并只读遍历：

| 对象 | 观察 | 证据层级 |
|---|---|---|
| `LI_C0_R.IDX` | 393,536 字节；32 字节/记录，共 12,298 条 | 全文件索引遍历 |
| IDX flag 0 | 4,169 条 | 全文件计数 |
| IDX flag 1 | 8,129 条 | 全文件计数；含义仅作为候选压缩标记 |
| IDX stored_size=0 | 2,505 条 | 全文件计数 |
| IDX 对齐 | 后一条 offset = 本条 offset + align256(stored_size)，全量相邻检查 0 个异常 | 全文件检查，不等同于 BIN 边界检查 |
| root.rdx | 360 字节，45 条 `<HHI>` 记录 | 全文件解析 |
| system.rdx | 40 字节，5 条 `<HHI>` 记录 | 全文件解析 |
| `0x4b13d561.fdata` | 264,309 字节，开头 `PDRK0000`，0x10 是 `IDRK0000` | 实际文件字节读取 |
| 上述 FDATA 第 2 条 KIDSOBJDB | entry offset=1184、entry size=157、packed=88、unpacked=96、flags=0x400000 | 实际文件 header 读取 |
| 上述记录压缩 | 10 字节 chunk 前缀 (`u16 length + 8 bytes`) + 76 字节 zlib + 2 字节零填充；输出 96 字节，以 `_DOK0000` 开头 | 真实原始压缩片段经 Python zlib 解码验证 |

**尚未验证：** 远程大型 `root.rdb`（5.75MB）和 `system.rdb`（1.83MB）的完整读取在本次连接中未成功；未恢复 `LD_C0_R.BIN`；还未完成任何全量压缩包恢复。因此不能声称 RDB/FDATA 全量提取或 LINKDATA 内容解码完成。

## 本轮代码

- `Scripts/unpack/core.py`：IDX/RDX/RDB 解析、IDRK 读取、KT zlib 分块解码、LINKDATA 标准 zlib 候选解码、文件来源追溯工具。
- `Scripts/unpack/inventory.py`：资源清单和 7z 多卷连续性、可选完整 SHA-256 和 `7z t`。
- `Scripts/unpack/linkdata.py`：LINKDATA 索引遍历、可选 BIN 原始提取和解压，`--limit/--start/--dry-run/--resume`。
- `Scripts/unpack/ktrdb.py`：root/system RDB/RDX 目录、FDATA/特殊 FILE 精确定位、IDRK 记录原始提取与 zlib 解码。
- `tests/test_unpack_core.py`：含真实 88-byte 压缩记录验证向量的 8 项单元测试。

## 后续实际验收计划

1. Runner/本地恢复 7z：逐卷校验、SHA-256、输出体积与磁盘空间；保留原始仓库输入。
2. 用 `M1` 运行恢复后的 `LD_C0_R.BIN`：抽检 flag=0、flag=1、空项和极端长度，校验完整索引边界，再逐批覆盖全部记录。
3. 用 `M2` 运行真实 RDB+FDATA：比对 root 60,722 条的历史审计基线并新增 system 目录，针对 ff03/fffe/独立 FILE 分类，不把缺失映射直接算成坏包。
4. 在解析报告中记录每条 `raw SHA-256`、`decode SHA-256`、输入文件 SHA-256、索引位置及错误码；选 3 种 KIDSOBJDB 样本验证 header 和数据大小。

本轮的真实样本是从 GitHub 连接读取后做受控验证；可回归测试使用的 88-byte 压缩向量不代表整包成功，不能用其掩盖还原失败。
