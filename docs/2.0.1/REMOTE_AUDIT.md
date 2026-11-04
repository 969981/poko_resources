# 2.0.1 仓库远端资源目录与索引实测（2026-11-04）

> 来源：`969981/poko_resources` 的 `2.0.1_unpack` 分支。下列结果通过 GitHub 目录数据和实际可读取的小型二进制索引计算。**并非全量解包成功报告。**

## M0 GitHub 目录与分卷

- 逐级列出 ExeFS、RomFS、KIDS_PLATFORM_OUNCE 及 MountPoint_1、MountPoint_2、data 子目录：**99 个文件**，文件字节数合计 **6,563,012,216**。
- 发现 **10 组 .7z 分卷 / 70 个卷文件**。GitHub 文件名中的卷号从 001 开始且连续，未发现断号。尚未下载所有分卷或运行 `7z t`，因此**压缩包完整性未验证**。
- 保留 `2.0.1/exefs/main`，未包含 `romfs/movie_asset/`。

## M1 LINKDATA 实际索引

- `LI_C0_R.IDX` 393,536 字节，按 `<QQQQ` 共 **12,298 条**。
- flag 0：**4,169**；flag 1：**8,129**；stored_size 为零：**2,505**。
- 检查所有相邻记录 `next.offset = current.offset + align256(current.stored_size)`，**0 个相邻偏移异常**。
- 未读到完整 `LD_C0_R.BIN`，无法核对最终 BIN 范围，也不能把 flags 分布当成解压成功数。

## M2 root / system 索引与实体容器

| RDX | 条目数 | GitHub 中找到的 FDATA 容器名 | 未找到 |
|---|---:|---:|---:|
| `root.rdx` | 45 | 22 | 23 |
| `system.rdx` | 5 | 2 | 3 |
| **合计** | **50** | **24** | **26** |

注：这是匹配 **FDATA 容器名称**（将 `.7z.001` 及其多卷归一化后）的结果，不代表 24 个容器已还原/内部有效。无法定位的条目可能是版本、安装分区或平台选装等原因，不可自行标注为“ROM 损坏”。

- `system.rdx` 匹配的两个 FDATA 为 `0x38f972af.fdata`、`0x52482d03.fdata`，它们不属于 root.rdx 的 45 个哈希。
- `root.rdb` / `system.rdb` 因当前大文件读取接口限制未完成**本轮直接解析**；已有历史只读审计值不能当作本轮提取率。
- `0x4b13d561.fdata` 的真实 IDRK KIDSOBJDB 第二条记录：FDATA offset=`0x4a0` (1184)，entry_size=157，packed=88，unpacked=96，flags=`0x400000`。
- 压缩载荷由 10 字节 chunk 前缀、76 字节 zlib 和 2 字节零填充构成，已用 Python zlib **真实解码出 96 字节**，输出开头为 `_DOK0000`。
- 实际压缩数据 SHA-256：`3a9ad1422a443971e041822417c2e74cdb5dce3c23e10d2524cb95ab94112c79`。
- 实际解压后 SHA-256：`d6e4be2e738194239339cf87307b5b61e9b6197f3fea9967ed726ff506f6e877`。

下一步以恢复后的真实游戏容器为输入运行 `Scripts/unpack`，将每条索引的 `LOCATED/EXTRACTED/DECOMPRESSED/FAILED` 状态写入报告，不基于仅有的文件名、头部或短样本宣布全部成功。
