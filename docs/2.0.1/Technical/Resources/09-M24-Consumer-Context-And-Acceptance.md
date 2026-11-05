---
title: M24 物品分类消费者静态矩阵与背包建造材料场景验证
tags: [pokopia, item, native, arm64, consumer, gdb, obsidian]
game_version: "2.0.1"
status: STATIC_VERIFIED_RUNTIME_PENDING
updated: 2026-11-05
---

# M24：原生物品分类的消费者、场景与验收

## 已执行：原版 2.0.1 M12/M20 消费者矩阵

来源为原版 NSO0 静态证据产物，验证 SHA 不变：

- ExeFS `main` SHA-256: `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`
- RomFS `00983.bin` SHA-256: `2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`
- [M12 消费者原始指令](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M12/item_id_lookup_0x26_original_evidence.json)
- [M20 真实两级调用者](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M20/m20_two_stage_item_callers.json)
- [M20.1 后续字段读窗口](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M20/m20_1_original_wrapper_caller_offsets.csv)

重建脚本：[m24_item_consumer_matrix.py](../../../../Scripts/resources/m24_item_consumer_matrix.py)，生成 [CSV](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M24/m24_wrapper_consumer_matrix.csv) 和 [JSON 汇总](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M24/m24_summary.json)。

| 证据项 | 原版静态统计 | 解释边界 |
| --- | ---: | --- |
| `main+0x2F1F0` 直接 BL 调用者 | 17 | 已确认控制流 |
| 近邻窗口中出现 `wrapper+8` 模式 | 12 | 尚未证明记录来源是 `00983.bin` |
| 近邻出现后续字段访问 | 13 | 仅限 12 指令窗口、源指针关联待证 |
| 近邻访问 `+0x3A` | 1（`0x49A048`） | 不能直接命名为 UI 分组 |
| 近邻访问 `+0x26` | 0 | 不代表没有消费者；M12 的独立循环已定位 |
| M12 独立 `+0x26` 原生读指令 | 2 | 物品类型字段候选，尚未恢复正式 enum |

M20.1 的近邻出现 `+0x0C`（3）、`+0x14`（2）、`+0x18`（1）、`+0x1E`（3）、`+0x27`（1）、`+0x3A`（1）、`+0x41`（2）。这些是原始指令的**字节偏移值**，不意味着所有访问均来自同一个 `00983.bin` 结构，也不代表相应 UI 功能已经识别。

从原始 M12 单独确认：
- `main+0xE5AA60` → `ldrb w0,[x8,#0x26]`；后续将其减 1 并与 `0x13` 比较。
- `main+0x10289F4` → `ldrb w21,[x8,#0x26]`；同一函数另有 `0x1028A38` 读取 `+0x39`。
- `main+0xABBB64`、`0xABBBD4` → 读取 `+0x3A` 并分别比较 `0x0F`、`0x15`。这不代表两个官方 enum 常量名称已知。

## 已直接从原始 00983.bin 回读的 3 条 68 字节基准

M24 的 [原始基线 CSV](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M24/m24_three_original_68byte_baselines.csv) 从当前分支真实 `decoded/00983.bin` 读取，保留完整原始十六进制、独立 SHA-256、名称索引和三个分类分组原值；生成器严格检查原版文件 SHA。

| item_id | 对照示例 | 原始记录文件位置 | 原始 `+0x26` | 原始记录 SHA-256 |
| ---: | --- | --- | --- | --- |
| 6 | 成熟的蘑菇 | `0x1D8` | `0x0F` | `c472dee6e10022fc65cbf5ceb07d4f45d276b93b0efd14b50401f125913364ab` |
| 101 | 藤蔓绳 | `0x1B14` | `0x10` | `38be25dae64879aa4b403c01a46f8dafca63a26820e750766e034f6e66a1735f` |
| 302 | 花朵靠垫 | `0x5078` | `0x04` | `ed7934f42c6cbb5377c285c4a9c488cd92d8b15ef1b1fb4c2c06b78292d3003b` |

**这三条属于原版 RomFS 静态基准，不是三条运行时 GDB 命中。** CSV 的 `runtime_full_68byte_match` 均为 `NOT_COLLECTED`，直到真正得到三个不同有效 ID 的完整内存记录后才可改成证据相关的验收状态。源记录 302 的名称应以九语言原生 catalog 最终对账为准；以上示例仅供辨认 `0x04` 组。

## 当前 3 个研究目标的真实状态

| 目标 | 本轮做到的工作 | 尚缺证据 |
| --- | --- | --- |
| 3 个不同 ID 的完整 68 字节一致 | M23 采集和逐字节审计就绪，可核对材料及非材料候选 | **0 条真实 GDB 运行时样本**，还没有 3/3 PASS |
| V2+0x30 真实目标、加载与分配 | M23 会读取动态 x2 和实际 vtable slot，并对每种新方法保存首 128 字节机器码和 SHA；M24 锁定 17 个上层调用者 | **没有运行时函数指针**；没有从 V2 的查表/分配连到原版 00983 |
| +0x26 在背包/建造/材料中的正式语义 | M23 支持人工阶段标记与 8 层调用栈；M24 保存原版候选调用点 | 没有原版 UI 场景三方对照、代码消费者的正式 enum 字符串或可重复行为证明 |

## 运行 2.0.1 后的证据收集操作

在 GDB 连接客体 ARM64 并确认实际 main 基址之后（路径必须替换）：

~~~gdb
source Scripts/resources/m23_gdb_trace_item_classification.py
pokopia_m23_start 0xYOUR_REAL_MAIN_BASE /absolute/path/main /absolute/path/00983.bin /absolute/path/m23_inventory.jsonl 10000
pokopia_m23_phase inventory
continue
~~~

在游戏内操作背包。需要切换到制作时先中断 GDB，保留第一份日志，再从新的文件重开：

~~~gdb
pokopia_m23_stop
pokopia_m23_start 0xYOUR_REAL_MAIN_BASE /absolute/path/main /absolute/path/00983.bin /absolute/path/m23_crafting.jsonl 10000
pokopia_m23_phase crafting
continue
~~~

接着分别对建造、材料消耗做同样采样：

~~~gdb
pokopia_m23_stop
pokopia_m23_start 0xYOUR_REAL_MAIN_BASE /absolute/path/main /absolute/path/00983.bin /absolute/path/m23_construction.jsonl 10000
pokopia_m23_phase construction
continue
~~~

可以使用标签 `materials`。**阶段名完全由操作者声明，并非自动从游戏代码识别**。每条命中记录返回地址、guest 调用栈、真实虚表槽位函数指针以及按 ID 回读的完整 68 字节；首次遇到的 V1/V2 动态方法还保存 128 字节机器码与 SHA，便于以后对照原始 ExeFS 并追踪 helper。采样断点会短暂影响运行速度；调试器可能使用软件断点更改可执行代码的断点指令，采集器本身不主动写入物品数据/存档。

分别离线校验：

~~~powershell
python -m Scripts.resources.m23_item_classification_audit --jsonl _work/m23_inventory.jsonl --out _work/audit_inventory.json
python -m Scripts.resources.m23_item_classification_audit --jsonl _work/m23_crafting.jsonl --out _work/audit_crafting.json
python -m Scripts.resources.m23_item_classification_audit --jsonl _work/m23_construction.jsonl --out _work/audit_construction.json
~~~

任何日志文件路径均应替换为实际采集位置。运行时最多允许多少次命中由 `pokopia_m23_start` 最后参数控制。游戏 UI 中的物品操作应选择差异明显的样本：6（食品，raw kind `0x0F`）、101（藤蔓绳，`0x10`）、302（家具倾向，`0x04`）；真正触发哪条记录由游戏决定，**不能强行假设三者会命中**。

## 三层验收，必须各自通过

**A. 记录身份**：真实 GDB JSONL 中至少三种不同有名称的有效 ID，其运行时数据与指定 SHA 的原始 `00983.bin` 同一 ID 的全部 68 bytes 一致，含一个原始 `0x10`、一个其他类别，有不同指针地址。无日志、源字段不吻合、只有单字节吻合、或 BSS fallback 均不算 PASS。

**B. V2 身份与真实加载**：动态 `v2_method` 必须与 `[vptr+0x30]` 中实际方法指针吻合；再在该精确函数上追踪 ID 寻址、helper、读入/解压与内存分配直到原始 00983 内容。仅有相同 68 bytes 仍不能证明 loader。

**C. 分类及业务语义**：至少针对背包展示、制作/材料扣除、建造需求检查三个实际行为，用场景阶段、调用栈分支和游戏内状态变化做交叉验证，并在原生汇编中找到字段读取到分发条件/位表的真实用途。有可追溯的 enum 名称/文本表再赋予正式分类标签；否则只保留 `raw_kind_u8`，不填官方名称。最大堆叠上限是独立调查任务。

## 静态重建与 CI

~~~powershell
python -m Scripts.resources.m24_item_consumer_matrix --out _work/m24
python -m unittest discover -s tests -p "test_m23_item_classification_audit.py" -v
~~~

M24 Actions 对原版来源与提交的 17 行矩阵进行再生成、严格对账；M23 Actions 只检查脚本与合成测试，均不连接游戏。不能将 CI 通过当作 A/B/C 的运行时证明。

[返回资源索引](README.md) · [[08-M23-Native-Category-Proof]]。
