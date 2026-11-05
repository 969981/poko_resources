---
title: 解包与转换故障排查
aliases: [解包错误排查, 格式验证清单]
tags: [pokopia, troubleshooting, validation, binary]
game_version: "2.0.1"
status: OPERATIONS_GUIDE
updated: 2026-11-05
---
# 常见失败、诊断顺序及验收

原则：先确认**文件是否存在、来源是否正确、索引范围是否正确**，再诊断算法或资源语义。保留失败状态和日志，不要为了通过校验而修改原始文件。

| 现象/状态 | 首先检查 | 安全处理 |
| --- | --- | --- |
| `7z t` 报 CRC / 缺分卷 | `.7z.001` 后续分卷是否同目录且编号连续、存储空间是否足够 | 补齐原始分卷，重新 `7z t`；不要手工拼无来源片段 |
| 找不到 `LD_C0_R.BIN` | 是否只下载了 `*.7z.001`，是否跑过真实恢复 | 先 7-Zip 解压到 `_work/`，不要给 `--bin` 传分卷 |
| `CONTAINER_NOT_PRESENT` | RDB/RDX 是否齐全；对应 FDATA 是否已恢复、是否位于平台/挂载目录 | 恢复缺失源；暂不归因于 codec |
| `DECODE_FAILED` | 索引偏移/长度、flag、原始字节、压缩方法与校验和 | 同时保存 raw 和失败日志；不能仅重命名为 decoded |
| `ModuleNotFoundError: PIL` | 当前 Python 环境的 pip 和模块解释器是否一致 | `python -m pip install "Pillow>=11,<13"` |
| G1T 签名或 platform 不符 | 文件是否真是 `*.g1t`，读入的是否为正确段 | 停止套用 `GT1G0600`/`0x18` 假设，记录新格式样本 |
| PNG 花屏、棋盘错位、颜色异常 | format、Ounce 布局、UV 顺序、mips、裁剪边界 | 先单张比较 `ounce2/8/16` 等候选，不能默认旧 `gobN` |
| PNG 全透明或候选来源不唯一 | alpha 分布、同名纹理不同 Hash、G1T 实体缺失 | 标记为原生候选并保留；不要删除透明图或任选源文件 |
| 纹理名数字与图鉴 ID 不一致 | TEXINFO 名称、KIDSOBJDB Hash 与原生 species 字段是否同一链 | `native_species_id_verified` 留空，等原生代码/数据双向证据 |
| 物品类别、堆叠上限疑似错配 | 是否把 `+0x26/+0x3A` 当成已确认枚举或把 255 当游戏上限 | 只输出原始值与候选，恢复实际消费者语义后再命名 |
| 文本错行/错语言 | `04645...04653` 文件顺序、空行、零基 ID、控制符 | 保留空槽/PUA/控制标签，用九语 validation 回归 |
| 字符串有内容但无剧情分类 | M7 仅恢复表内 ID；缺实际对象/脚本外键 | 保持 `UNKNOWN`，先补 RNK 原始资源与原生读取者 |
| .NET 编译失败 | SDK 10、`ThirdParty/Edoke` 子模块、Git 修订 | `git submodule update --init --recursive ThirdParty/Edoke`；不要删 Python 管线 |
| SQLite 表/列不存在 | 构建产物版本、实际 `.schema` | 检查 schema 再查询，不凭旧截图编造字段 |

## 本地回归测试

```powershell
python -m unittest discover -s tests -v
python -m Scripts.unpack.smoke --source 2.0.1 --output _meta/2.0.1/smoke
python -m Scripts.unpack.full_pipeline --source 2.0.1 --work _work/2.0.1-verify --output _meta/2.0.1/full --sevenzip 7z --verify-only
dotnet run --project Pokopia.Binary.Checks -c Release
```

全量 `full_pipeline` 需要较大磁盘空间与已恢复/可恢复的原始分卷；它的 `--verify-only` 是强制参数，目的为出具验证报告而非发布素材。先用小样本 smoke 再考虑全量。

## 独立核验原始数据 SHA

```powershell
Get-FileHash -Algorithm SHA256 "2.0.1/exefs/main"
Get-FileHash -Algorithm SHA256 "UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin"
```

与 [[01-Source-Layout]] 的指定版本 SHA 核对；若不同，不应继续复用已确认偏移或“1,333/4,600”等特定版本结论。

## 输出验收检查单

- [ ] 输入路径、版本、完整 SHA 和数据来源记录完整
- [ ] 索引偏移/长度边界无越界；失败条目与缺失条目仍可统计
- [ ] `raw` 与 `decoded` 没有混淆，`verify-only` 不被误解为已产出素材
- [ ] 纹理记录 G1T/TEXINFO/UV/layout/PNG SHA 互相能追溯
- [ ] 文本九语言行号、空槽、UTF-8、控制符得到保护
- [ ] E0–E5 证据等级与身份验证状态独立填写
- [ ] 新增结论有成功样例、反例和最短复现命令

请勿重走已被 [M20 证明是 OpenSSL 的 NID 983](../M20_ITEM983_CACHE_ORIGIN.md) 错误调用链。验证规则见 [[08-Evidence-And-Open-Questions]]。
