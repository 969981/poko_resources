---
title: 原生格式字段与读取步骤
aliases: [Pokopia 格式详解, 二进制格式卡片]
tags: [pokopia, binary, rdb, fdata, kidsobjdb, texinfo, g1t]
game_version: "2.0.1"
status: PARTIAL_FORMATS
updated: 2026-11-05
---
# 原始文件格式卡片：先看头，再取字段

下列格式卡片有意把**已经读取的结构**与**尚未证明的语义**分开；不因能解包/解码，就推断材料类型、物种 ID 或剧情文本外键。更多总览：[[02-Binary-Formats]]。

## 1. LINKDATA：IDX 和 BIN

- 原始索引：`2.0.1/romfs/LI_C0_R.IDX`。
- 原始负载：恢复分卷后的 `LD_C0_R.BIN`；保留未解码 raw。
- 实现：`Scripts/unpack/linkdata.py`，先 `--idx` 索引，必要时传 `--bin`、`--decode`、`--resume`。
- 结果：按条目编号导出 `NNNNN.bin`；具体以原始索引条目号为准，不能按文件名猜内容。
- 验收：记录索引字节区间、压缩标志、raw/decoded 长度和 SHA；解码失败要保留失败状态。

```powershell
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --output _meta/2.0.1/linkdata
```

## 2. KT 索引、FDATA 和 IDRK

- 原始组合：`root.rdb/root.rdx` 与 `system.rdb/system.rdx`，再按 RDX 位置、目录挂载规则定位真实 `0x<hash>.fdata`。
- 已审计的 RDX 索引条目宽度为 **8 字节**；IDRK 资源记录头为 **48 字节**；RDB footer 存在不同宽度（研究实现包含 13/17 字节处理），未知类型保留 opaque。
- `Scripts/unpack/ktrdb.py` 可按原始索引尝试提取、KT framed zlib 解码、记录来源。
- `Pokopia.Binary.Cli audit-fdata` 只检查索引与物理 FDATA 中 IDRK 头的 Name/Type Hash、大小等对应；`VERIFIED_IDRK_HEADER` 不是全文解码成功。

```powershell
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _meta/2.0.1/ktrdb
dotnet run --project Pokopia.Binary.Cli -c Release -- audit-fdata PATH_TO_ROOT.RDB PATH_TO_ROOT.RDX PATH_TO_FDATA_DIRECTORY
```

若某份 FDATA 不存在，记 `CONTAINER_NOT_PRESENT`，不要补造原始内容，也不要视为格式解码失败。

## 3. KIDSOBJDB

- 入口：`Scripts/unpack/decode_kidsobjdb.py`；大文件只读对照：`Pokopia.Binary.Cli kids` / `kids-fields`。
- 已识别 `_DOK0000`、IDOK / RDOK 等对象/属性结构。对部分原生固定宽类型可保留字节偏移、数量、小端值；未知类型或 RDOK 字段语义保持未定。
- 必须同时记录 `property_name_hash`、`property_type_hash`、原始 offset 和对象来源；仅数值相等产生的是**候选边**。

```powershell
python -m Scripts.unpack.decode_kidsobjdb --input PATH_TO_KIDSOBJDB --output _meta/kidsobjdb-sample.json
dotnet run --project Pokopia.Binary.Cli -c Release -- kids-fields PATH_TO_KIDSOBJDB 8
```

## 4. TEXINFO（已核验定长记录）

文件头 **4 字节小端 u32 count**，后接 **每条 104 字节**；长度公式 `4 + count × 104`。

| 每条记录偏移 | 数据 | 状态 |
| --- | --- | --- |
| `+0x00` | 64 字节 NUL 终止/截断纹理名 | 已解析 |
| `+0x40` | u32 图层/条目号 | 已解析，解释要按具体图集 |
| `+0x44` | 8 个 float32，四顶点 UV | 已解析 |
| `+0x64` | u32 尾字段 | 语义 UNKNOWN |

原版样本 `root_042753_b4b1fe49.texinfo`：**1,333 条**，使用 `Scripts/resources/g1t_to_png.py` 中 `parse_texinfo()`，不要只读第一条。

## 5. G1T/Ounce 贴图

- 原始 G1T 样本签名 `GT1G0600`，平台 `0x18`；按容器头、偏移表、format、尺寸、mips 和 payload 读取。
- 已有原生样本：`0x66`（BC7）、`0x0A`（BGRA8888）；部分其他格式仍须逐一验证。
- Ounce 块线性恢复要匹配布局 `ounce1/2/4/8/16/32`，不是旧 `gobN` 的替换名称。
- 使用 TEXINFO 的**真实 UV** 做裁剪，再核验 PNG 的尺寸、透明度、SHA，记录 G1T/TEXINFO 双源 Hash。

与输出流程相连：[[04-Texture-Pipeline]]、[[12-Reproducible-Recipes]]。

## 6. 物品原始表与九语言文本

- `LD_C0_R.BIN/decoded/00983.bin`：**64 字节头 + 4,600 × 68 字节记录**。
- 第 `item_id` 条原始记录位置：`64 + item_id * 68`，需先检查边界。
- 已通过九语言数据对账的是 `+0x22` 名称索引；`+0x26 / +0x39 / +0x3A` 有原生读取证据，但不能据此赋予“官方材料枚举/堆叠上限”语义。
- 名称表：`04645.bin`～`04653.bin`，具体语言表见 [[05-Localization]]、[[13-Resource-Provenance-Map]]。
- 特别注意：ExeFS 中 OpenSSL **NID 983** 的调用链不属于物品 `00983.bin`，见 [M20 反证](../M20_ITEM983_CACHE_ORIGIN.md)。

## 文件格式验收记录建议

每种格式笔记至少填写：原始路径、版本、字节数/SHA、magic、端序、记录数、字段偏移、使用脚本与命令、成功和失败样本、下游来源路径、未解语义。复制 [[09-Research-Template]] 记录新增发现。
