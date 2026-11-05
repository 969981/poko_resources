---
title: 原生二进制格式与读取
tags: [pokopia, binary, linkdata, rdb, kidsobjdb, g1t]
updated: 2026-11-05
---
# 二进制格式速查与解析边界

| 格式 | 输入或实例 | 读取入口 | 已知状态/限制 |
| --- | --- | --- | --- |
| `.7z.001` | LINKDATA BIN、FDATA 分卷 | 7-Zip `t`、`x` | 先恢复所有分卷再解析容器 |
| `LI_C0_R.IDX` | LINKDATA 索引 | `Scripts/unpack/linkdata.py` | 记录索引、偏移、flags；具体 codec 必须验证 |
| `LD_C0_R.BIN` | LINKDATA 负载 | 同上、`publish.py` | 逐条导出 `NNNNN.bin`；不能按索引声称已解码 |
| `root/system.rdb, .rdx` | KT 资源索引 | `Scripts/unpack/ktrdb.py` | 建立指向 FDATA 的物理记录 |
| `.fdata` | 资源容器 | `ktrdb.py`、`publish_stream.py` | 依据索引取字节、解码、SHA/长度对账 |
| `.file` | 独立资源 | `ktrdb.py` | 原始字节可保存；内部语义需要单独解析 |
| `KIDSOBJDB` | `*.kidsobjdb` | `decode_kidsobjdb.py`、`m4_batch.py` | IDOK/RDOK/属性结构，可读不等于字段语义成立 |
| `.texinfo` | 纹理名称、图集坐标 | `g1t_to_png.py` | 记录名、层号、UV，可用于原生裁剪 |
| `.g1t` | `GT1G0600` 容器 | `g1t_to_png.py` | Switch 2 `platform=0x18`、Ounce 排列 |
| `00983.bin` | LINKDATA 原生物品表 | `analyze_native_item_fields.py` | 64 字节头 + 4,600 × 68 字节记录；部分字段仍未知 |
| 原生文本表 | `04645.bin`–`04653.bin` | `recover_native_text_ids.py` | 九语言物品名称已核验；其他表外键未闭合 |
| BFBS/FlatBuffers | 候选格式 | M3/M9 工具 | 不能把其他游戏的 BFBS 文件名当成本游戏证据 |

## TEXINFO 结构（已在 M5 原生样本验证）

整体为**小端 u32 记录数 + 104 字节定长记录**：总长度 `4 + count × 104`。

- `+0x00`：64 字节、NUL 截断的纹理名称；
- `+0x40`：u32，图层/条目号；
- `+0x44`：8 个 float32，对应四个顶点 UV；
- `+0x64`：u32 未知尾字段，不能擅自命名。

`root_042753_b4b1fe49.texinfo` 有 1,333 条记录，使用 `parse_texinfo()`，不要只解析第一条。

## G1T（已核验的 0x18 平台）

签名 `GT1G0600`；按真实容器头、纹理数量、偏移表和每条 format/尺寸/mips/payload 解析。已知原生样本包括 `0x66`（BC7）、`0x0A`（BGRA8888）；部分 BC3/DXT5 是支持的候选，**不是说任意 G1T 都可直接解码**。

`0x18` Ounce 的块内地址排列与旧 Tegra `gobN` 不同；验证使用 `ounce1/2/4/8/16/32`，保留传统 `gobN` 仅用于对比。详见 [[04-Texture-Pipeline]]。

## 原生物品表

`00983.bin` 文件长度满足 `64 + 4600 × 68`。第 `i` 条偏移 `64 + i × 68`（`i` 从 0 开始，需边界检测）。`+0x22` 是已经通过九语言文本对账的名称索引；`+0x26`、`+0x39`、`+0x3A` 有原生消费者读取证据，但**未证明**为正式材料类型/最大堆叠数。`00983.bin` 的编号与 OpenSSL NID 983 同数，是两个不同含义：参见 [M20 原始字节反证](../M20_ITEM983_CACHE_ORIGIN.md)。

详细原始字节证据：[M5 格式报告](../M5_NATIVE_TEXTURE_PIPELINE.md)、[M17–M19 原生字段](../M17_M19_NATIVE_ID_AND_ITEM_ENUM_STATUS.md)、[M3 RDOK](../M3_RDOK_DIRECT_EVIDENCE.md)。