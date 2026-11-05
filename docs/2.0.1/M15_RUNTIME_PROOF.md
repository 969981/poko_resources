# M15 — 2.0.1 原生物品 00983 与游戏实际消费者的运行时证据

## 为什么需要 M15

M12 已通过原始 NSO0 **23 条精确指令**证实以下行为：

`4600-ID 循环 W20 → 虚函数表 +0x30 按 ID 查资源对象 → 返回对象 +0x08 指针 → 读取该指针 +0x26`。

独立的 `romfs/LD_C0_R.BIN/decoded/00983.bin` 是 64-byte 表头 + 4600×68-byte 原始物品记录，`+0x22` 名称索引已核验九语言，`+0x26=0x10` 的 48 项几乎全部为公开资料中的制作/收集材料。但仍有一个关键缺口：**M12 返回对象的 +0x08 指针究竟是否指向 00983.bin 的记录？** 单靠 `4600` 次循环和 `+0x26` 位移匹配不能替代该证明。

M15 提供**只读、自动继续**的 GDB Python 检查点，比较返回对象指向的整条 68 字节记录与本分支原版 `00983.bin` 的对应物品 ID。既不修改模拟器内存，也不修改游戏 ROM/存档。

## 原生静态位置

| 2.0.1 ExeFS RVA | 原版指令/状态 | 所需寄存器 |
| --- | --- | --- |
| `main+0xE5AA60` | `ldrb w0, [x8,#0x26]` 前 | `x20` = 当前 ID，`x8` = 返回对象记录指针 |
| `main+0x10289F4` | `ldrb w21, [x8,#0x26]` 前 | `x20` = 当前 ID，`x8` = 返回对象记录指针 |

**文件身份要求**：

- ExeFS `main` SHA-256：`8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`。
- 原始 `00983.bin` SHA-256：`2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`。
- ROM 2.0.1、ARM64 guest 调试，`main_base` 必须来自**当前运行中** ExeFS 的真实模块起始地址。不能把 GitHub 文件偏移、宿主 CPU 地址或别的 Build ID 的偏移代进去。

## GDB Multiarch / 模拟器执行

确认 GDB 已连接游戏**guest ARM64** 进程，且运行到能正常读取 `x20/x8` 的状态。将源码与 `00983.bin` 放在 GDB 可以访问的路径。

```gdb
source Scripts/resources/m15_gdb_verify_item983_runtime.py
pokopia_item983_verify 0xYOUR_REAL_MAIN_BASE /absolute/path/to/00983.bin /absolute/path/to/item983_evidence.jsonl 150
continue
```

上例中的 `0xYOUR_REAL_MAIN_BASE` 是占位符，必须替换为实际十六进制地址。**不要**直接照抄或自行猜测内存映射地址。如果游戏已在执行中，安装断点后正常继续；脚本 `stop()` 返回 False，采样时自动恢复运行，超过 150 次命中自动关闭。

提前结束：

```gdb
pokopia_item983_stop
```

## 验收与反证

每个命中都输出 JSONL 一行，包含：

- 原始数据和实际运行时记录地址、ID、各自 68-byte SHA-256；
- 整条 68 字节是否一致、逐字节不同数量；
- `+0x22`、`+0x26`、`+0x39`、`+0x3A` 的原始/运行时值；
- 原始表和 ExeFS 版本哈希、原生断点 RVA；
- `ORIGINAL_BYTES_RUNTIME_68B_MATCH` 或 `RUNTIME_POINTER_UNRESOLVED_OR_TRANSFORMED`。

**建议至少采集 3 个不同有效 ID，其中含 1 个 `+0x26=0x10` 的原生材料候选及 1 个其他分组**，且两处消费者指向的内存均能读取。如果整条记录吻合，可建立“返回对象关联到原版 00983 记录”的很强运行时依据；仍需补充 **资源加载模块/表分配者** 才能严格证明数据来源路径。如果仅 `+0x26` 一个字节相同、而 68 字节不匹配，应标为未证明或运行时布局变换，不能硬判断为同一结构。

**尚未完成**：本仓库的静态 GDB 脚本不会自行连接游戏或产生运行时验收数据。没有真实 GDB JSONL/完整调用者证据之前，`00983 loader`、官方 `ItemKind` enum 名称、宝可梦 `species_id`→G1T 绑定仍标记未验证。

## 物种 ID 的进一步断点选择

M13 解析原版 rodata 的 910 个相关名称和 571 个 ARM64 字符串引用；`pokemon_dex_id` 在 `main+0x1136AA4` 被传给格式化/序列化式调用，与纹理资源哈希加载**尚无直接引用证据**。其他 `m_mainPokemonList` 与 `m_craftMainHelpPokemonKind` 等字串主要在成员读写、枚举/日志式路径被使用。**不要**把这些字符串使用点直接设为“物种图标加载成功 Hook”。

下一步需要找到资源加载器真正请求 TEXINFO/G1T Hash 的函数，观察输入的物种/形态 ID，再经同资源 Hash 对账 `Pokemon/pokemon_identity_crosswalk.csv`。没有这组原生调用证据时，继续保留全部 609 个物种 ID 空值。
