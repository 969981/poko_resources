# M23 / M23.1 — FF03 物理容器与原生 KIDS 对象消费者

> Pokopia 2.0.1 · 分支 `2.0.1_unpack` · 原始 ROMFS/RDB/RDX、KIDSOBJDB 与 ExeFS NSO 静态证据。只将源字节能证明的结论写成事实，不推断物种/村民 ID。

关联：[[M22_VILLAGER_NATIVE_SOURCE_AUDIT]] · [[M21_NATIVE_AUX_ICONS]] · [[M20_NATIVE_SPECIES_ITEM_CALLGRAPH]] · [[FULL_UNPACK_STATUS]]

## 1. 原始 RDX 平台与缺失 FDATA

原始源：`2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/root.rdx` 和 `root.rdb`。

- root.rdx SHA256：`22a38306a19d7311e4c282b72714994a162a3e9c63454f9cc7caed38d614c5cd`
- root.rdb SHA256：`47f715d98cbe8718ce0c5e51dd4666c6587796a51f72b904a76bde8d227be786`
- RDX 45 项，root RDB 60,722 项。
- 原始 RDX 的 FF03 项有 10 个，**当前 Git 仓库均没有同名物理 FDATA 或首个 7z 分卷**。现有 `Scripts/unpack/core.py:find_fdata()` 不能证明 FF03 对应 MountPoint_3 或某个游戏机平台；仅可标为原始标记 FF03。

| RDX 位置 | 物理文件 | 原始平台标记 | RDB 总记录 | G1T | KTID |
| ---: | --- | --- | ---: | ---: | ---: |
| 5 | `0x03a38715.fdata` | FF03 | 623 | 227 | 180 |
| 44 | `0xfd6af828.fdata` | FF03 | 525 | 294 | 133 |
| 合计 | | | 1,148 | **521** | 313 |

每条源记录已经由原始 root.rdb、root.rdx 和 `missing_input_records.csv` 逐项核验：name_hash、type_hash、记录号、未压缩大小、物理偏移、RDX 所属容器。未实际取得源 FDATA 字节，所以**没有任何本轮新解码的 G1T**。

相关文件：

- [45 条原始 RDX](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M23/m23_original_rdx_platform_inventory.csv)
- [521 条 G1T 逐项原始索引](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M23/m23_521_missing_g1t_original_rdb.csv)
- [原始输入总报告](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M23/m23_platform_source_report.json)

## 2. 已有 TEXINFO / KIDSOBJDB 的直接关联检查

以 521 条原生 G1T 的 `name_hash` 对照：

1. `Resources/Textures/Indexes/layout-textures.tsv` —— 已索引的 KIDSOBJDB→资源 Hash。
2. `Resources/Textures/Indexes/native_misc_texture_index.csv` —— 4,348 条非宝可梦 TEXINFO。
3. `Resources/Pokemon/pokemon_texture_index.csv` —— 609 条宝可梦 TEXINFO。

**521/521 没有在这三个现有索引中找到直接 G1T Hash 命中**（状态：`NO_LINK_IN_THREE_EXISTING_SOURCE_INDICES`）。

这是范围有限的负结果：**不能据此认定 521 条包含或不包含剩余 79 张村民头像**。必须先取得与 2.0.1 匹配的原始 FDATA/KTID，确认平台和 IDRK 字节之后再继续分类。

## 3. M23.1 — 原始 BSS 对象→方法表→属性选择方法的静态链

原始 `2.0.1/exefs/main` SHA256 为 `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`。

在源 NSO 的真实 ARM64 指令中已经确认：

| 原始 PC (main+) | 原生指令／语义 |
| --- | --- |
| `0xBB85AC` | `adrp x1, #0x3496000` |
| `0xBB85B0` | `adrp x8, #0x3496000` |
| `0xBB85B4` | `ldr x1, [x1, #0x3b0]` — 来源全局指针单元 `0x34963B0` |
| `0xBB85B8` | `ldr x8, [x8, #0x3b8]` — 方法表指针来源单元 `0x34963B8` |
| `0xBB85C8` | `add x8, x8, #0x10` |
| `0xBB85CC` | `stp x8, x9, [x1]` — 向所指对象内存安装方法表指针 |
| `0xBB85F8 / 0xBB8600` | `mov / movk` 组合出类型 Hash `0x79991E79` |
| `0xBB8604` | `b main+0x1FDC1E0` — 精确尾部分支目标 |

原始初始化指针关系（全部为 main 相对地址）：

```text
[0x34963B0] = 0x366E6F0    # 对象地址
[0x34963B8] = 0x32F0ED0    # 方法表初始指针
                  +0x10 -> 0x32F0EE0 (安装的方法表地址)
                  +0x18 -> 0x32F0EF8 (方法槽)
[0x32F0EF8] = 0xCE854C     # M20.2 的三属性 Hash 选择方法
```

`main+0x366E6F0` 已验证落入原始 NSO BSS：`main+0x34CBEC0` ～ `main+0x3D20000`。附近生成的 `0x79991E79` 与 M19 已验证 KIDSOBJDB 源对象和目标纹理对象的 type_hash 相同。

**这是一条精确的静态注册/安装路径，不是已经命中运行时执行的证据，更没有证明任何特定村民/物种 ID**。从 M19 的 603 条原生源→目标对象引用来看，9 张歧义头像的 54 条变体来源都已关联到纹理对象，但正式 game-ID 绑定数仍为 0。

- [方法表安装与原生 BSS 字节证据](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M23/m23_1_original_kids_table_install.json)
- [全局指针与属性消费者候选](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M23/m23_original_property_consumer_triage.json)
- [ARM64 计算地址记录](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M23/m23_property_pointer_code_xrefs.csv)

## 4. 复现及输入补齐

自动运行：[M23 GitHub Actions](https://github.com/969981/poko_resources/actions/workflows/unpack-m23-original-fdata-consumer.yml)。

```bash
python -m pip install "lz4>=4,<5" "capstone>=5,<6"
python -m Scripts.resources.m23_platform_fdata_audit
python -m Scripts.resources.m23_native_portrait_consumer_triage
python -m Scripts.resources.m23_1_native_kids_table_install
```

已附 Windows **只读**本地查找脚本，支持单文件和 `.7z.001/.002` 分卷，默认不计算哈希，显式 `-IncludeSHA256` 时计算文件 SHA256：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Scripts\unpack\Find-M23OriginalFDATA.ps1 -Root "D:\your\Pokopia\romfs" -IncludeSHA256
```

这个命令不会复制/上传任何 ROMFS 文件。只有源文件身份、挂载路径、原始版本及 IDRK 数据校验通过后，才可以新增原始输入重新跑 M2/M3/M5。不能将别的游戏版本中同名 FDATA 硬塞进 2.0.1。

## 5. 下一阶段可真正闭合的两条链

**来源恢复：** 优先找齐 `0x03a38715.fdata` 和 `0xfd6af828.fdata`，逐条验证 521 个 IDRK，再从新的 KTID/TEXINFO/ObjectDB 恢复真实名称与 PNG；将 79 张未匹配参考头像重新对账。

**原生消费者：** 在运行时追 `main+0xBB85CC` 安装写入和 `main+0x366E6F0` 对象真实内容，再追 `main+0x1FDC1E0` 的类型 Hash 注册者及 `main+0xCE854C` 的间接属性方法，最后定位 `game villager ID → source OID → target texture OID` 的读取边。缺少动态回读和原生身份字段时，只能标记 `UNVERIFIED`。
