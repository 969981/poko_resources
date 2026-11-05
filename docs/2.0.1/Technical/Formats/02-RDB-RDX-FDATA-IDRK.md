---
title: RDB/RDX/FDATA/IDRK 字节布局
tags: [pokopia, 2-0-1, rdb, rdx, fdata, idrk]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---
# KT 资源索引：RDB / RDX / FDATA / IDRK

源码：[core.py](../../../../Scripts/unpack/core.py)、[ktrdb.py](../../../../Scripts/unpack/ktrdb.py)。入口目录为恢复后的 `romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/`，含 `root.rdb`、`root.rdx`、`system.rdb`、`system.rdx` 及物理 `0x????????.fdata`。

## 1. RDX（每条 8 字节）

`struct.Struct('<HHI')`，位置由零基行号确定：

| 偏移 | 类型 | 字段 |
| --- | --- | --- |
| `+0x00` | u16 | `fdata_index` |
| `+0x02` | u16 | `platform_flags` |
| `+0x04` | u32 | `fdata_hash`，对应 `0x{hash:08x}.fdata` |

`find_fdata` 已知挂载根：默认目录、`MountPoint_1`、`MountPoint_2`；`0xffff/0xff01/0xff02` 有预选目录规则。未知 flags 应遍历已知根并要求唯一命中；**不可把未命中解释为数据不存在于游戏**。

## 2. RDB 文件头（32 字节）

`+0x00`：ASCII `_DRK0000`（8 字节）；`+0x08` 开始四个小端 u32：`header_size=32`、未定字段、记录总数、`header_hash`。每条 RDB 记录起始为 `IDRK0000`、至少 48 字节头；记录间以 **4 字节**对齐。

| IDRK 记录头偏移 | 类型 | 含义 |
| --- | --- | --- |
| `+0x00` | 8 bytes | `IDRK0000` |
| `+0x08` | u64 | `entry_size` |
| `+0x10` | u64 | `payload_size`（RDB 记录尾部 metadata/footer 长度） |
| `+0x18` | u64 | `unpacked_size` |
| `+0x20` | u32 | `entry_type` |
| `+0x24` | u32 | `name_hash` |
| `+0x28` | u32 | `type_hash` |
| `+0x2c` | u32 | `flags` |

这里的 `payload_size` 是 **RDB 解析器对尾区宽度的字段命名**，不要直接视作完整解压后数据长度。

## 3. 两种已实现 footer

- **13 字节**：`<HIIHB`，分别为 footer magic、容器内 offset、长度、RDX position、tail。
- **17 字节**：`<HIIIHB`，增加标记位；当前仅接受 `magic=0x0401`、`marker=0x80000000`、`tail=0`、有效 RDX position、16 字节对齐的受限布局。
- 其他 17 字节内容标 `opaque_17`；其他长度标 `opaque_N`，保留 hex，不虚构字段含义。
- 当前分支 `0x0401` 按 FDATA 内 IDRK 路线读取，`0x0c01` 走 standalone `data/0x<name_hash>.file`；不能混为一类。

## 4. FDATA 内的真实 IDRK

`read_idrk` 用 `<8sQQQIIII` 读取 48 字节头：magic、entry_size、packed_size、unpacked_size、entry_type、name_hash、type_hash、flags。头之后还可能存在元数据；计算 `metadata_len = entry_size - 48 - packed_size`，必须满足边界检查。

`decode_kt_payload`：若打包与解包长度相等，则读取原样；否则按 flags 选择 KT framed zlib chunk header（4 或 10 字节），校验完整 zlib 流与输出总长度。**IDRK 头匹配不意味着底层语义已识别**。

## 5. 只读复现

```powershell
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _meta/2.0.1/ktrdb
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _work/ktrdb-example --extract --decode --limit 20 --resume
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _meta/ktrdb-audit --extract --decode --verify-only --only-fdata 4b13d561 --limit 250
```

状态需区分 `CONTAINER_NOT_PRESENT`、`UNSUPPORTED_FOOTER_LAYOUT`、提取成功与解码成功。不能因为本地缺少分卷/FDATA 就写“解析器不支持格式”。

相关：[[03-KIDSOBJDB-IDOK-RDOK]]、[[04-TEXINFO-G1T]]、[[../Workflows/01-Restore-And-Decode]]。
