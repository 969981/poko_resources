---
title: M23 原生物品分类验证：两级虚表与68字节运行时对账
tags: [pokopia, 2-0-1, item, native, gdb, hex]
game_version: "2.0.1"
status: RUNTIME_NOT_YET_EXECUTED
updated: 2026-11-05
---

# M23：物品分类的最短下一阶段验证

当前最大阻塞：虽然原版 ARM64 的 `0xC7 注册表 → V1+0x38 → V2+0x30(item_id) → wrapper+8 → +0x26/+0x39/+0x3A` 调用已确认，但**没有证明 wrapper+8 指向的 68 字节数据来自原版 `00983.bin`**。

另一条编号 983 的描述符在 M22 已被证明是 OpenSSL `md_gost12_512`，与 LINKDATA 条目 `00983.bin` 无关。请不要重走这条被反证的路径。

## 最有价值的两个动作

1. 动态读取 **V1+0x38 / V2+0x30 的实际虚函数目标地址**，绕开海量的静态候选虚表；后续再沿具体函数的构造、分配、解码、索引查询找物品表来源。
2. 在读取 `+0x26` 和 `+0x3A` 时，把现场内存的**完整 68 bytes** 与 SHA-256 固定的 `00983.bin` 同一 item_id 记录逐字节对账，不接受仅一字节匹配。

### 原生静态断点（2.0.1 ExeFS RVA）

| 原始代码 | 寄存器/作用 | 已证等级 |
| --- | --- | --- |
| `main+0x2F238` | x0=V1 对象，x8=V1+0x38 的真实方法指针 | 动态目标待采 |
| `main+0x2F258` | x0=V2 对象，x8=V2 虚表，x2=V2+0x30 的真实方法指针，x1=item ID | 动态目标待采 |
| `main+0xE5AA60` | x20=item ID，x8=记录候选指针，读取 +0x26 | 静态指令已证 |
| `main+0x10289F4` | x20=item ID，x8=记录候选指针，读取 +0x26 | 静态指令已证 |
| `main+0xABBB64` | x19=item ID，x8=记录候选指针，读取 +0x3A | 静态指令已证 |

程序输入严格限定原始版本：
- `2.0.1/exefs/main` SHA-256 = `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`。
- `UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin` SHA-256 = `2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`。

## GDB 调试（仅做只读数据采集，自动继续）

需要运行 Pokopia 2.0.1 的 guest ARM64 调试进程。获取当次真实 `main` 模块基址，**不可把宿主地址或不同 BuildID 的基址代入**。GDB 必须能读取 x0/x1/x8/x19/x20 及 guest 内存。

~~~gdb
source Scripts/resources/m23_gdb_trace_item_classification.py
pokopia_m23_start 0xYOUR_REAL_MAIN_BASE /absolute/path/2.0.1/exefs/main /absolute/path/00983.bin /absolute/path/m23.jsonl 500
continue
~~~

脚本先校验两个磁盘文件 SHA/长度，再布置五个 GDB 断点。命中自动继续，并将 `v1_method`、`v2_method`、实读虚表槽位、guest 调用栈、实验阶段标签、寄存器对象指针和 68-byte 现场内存 Hex 记为 JSONL。采集器不主动写入物品数据、ROM 或存档；但调试器的软件断点可能临时修改客体代码指令。

需要提前停采：

~~~gdb
pokopia_m23_stop
~~~

> 磁盘 SHA 通过 **不等于**模拟器加载的客体模块身份已被独立证明；用户必须另外核验 guest BuildID、映射基址/运行版本。GDB 断点会短暂打断执行，可能减慢模拟器。

## 离线证据验收

在普通 Python 环境运行（不需要 GDB 包）：

~~~powershell
python -m unittest discover -s tests -p "test_m23_item_classification_audit.py" -v
python -m Scripts.resources.m23_item_classification_audit --jsonl _work/m23.jsonl --source UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin --out _work/m23_audit.json --min-distinct 3
~~~

M23 新增 `pokopia_m23_phase inventory`、`pokopia_m23_phase crafting`、`pokopia_m23_phase construction`、`pokopia_m23_phase materials`，用于在调试暂停时标记当前**人工声明**的实验场景；`guest_call_stack` 包含最多 8 层调用点，`v1_vtable_slot_agrees` / `v2_vtable_slot_agrees` 用于将动态方法指针与实际虚表内存槽位交叉核验。**人工阶段名称不是原生 UI 逻辑的证明**。完整分场景流程见 [[09-M24-Consumer-Context-And-Acceptance]]。

路径需与 GDB 记录实际输出一致。判为 `RUNTIME_68B_RECORD_IDENTITY_SUPPORTED__LOADER_UNPROVEN` 的条件：至少三个不同且有原生名称索引的有效 ID 完整 68-byte 一致、具有不同内存记录指针，并涵盖至少一条 `+0x26=0x10` 材料候选及另一种类别。任何单字节不符、只有 fallback、缺少独立 ID 不能提升证据等级。若程序未运行、没有真实 JSONL，状态只能是 `INSUFFICIENT_RUNTIME_RECORD_EVIDENCE` 或 `RUNTIME_NOT_YET_EXECUTED`。

测试和工作流：
- [GDB 数据采集脚本](../../../../Scripts/resources/m23_gdb_trace_item_classification.py)
- [离线校验器](../../../../Scripts/resources/m23_item_classification_audit.py)
- [合成记录回归测试](../../../../tests/test_m23_item_classification_audit.py)
- [M23 GitHub Actions](https://github.com/969981/poko_resources/actions/workflows/unpack-m23-item-classification-probe.yml)

GitHub CI **只能检测 Python 语法和合成样本算法**，不能替代真实 GDB 命中。文档提交时未运行真实模拟器动态测试。

## 后续要追的语义

1. 取得实际 `v2_method` → 对其原始 ARM64 函数进行受限分析（下层 helper、查表、内存分配）。结合实际 wrapper+8 指针，追到 `00983.bin` 字节从哪里写入。
2. 首次完整闭合后，再追踪 `+0x26` 在背包/建造/材料检查等消费者中的分支语义，寻找官方 enum / 字符串 / 类型表，不以“名字像材料”代替原生证据。
3. 重点用 `0x04` 家具、`0x0A` 种子、`0x0F` 食品、`0x10` 材料和混合组 `0x06`、`0x12` 做正反例；`+0x39/+0x3A` 应独立考证，不能默认与 `+0x26` 同义。
4. 最大堆叠上限另走背包数量读取、堆叠合并、写入限制的独立调用链；`uint8` 的 255 可表达范围不代表游戏允许值。

原始证据：[M11](../../M11_NATIVE_ITEM_CONSUMERS.md) · [M15](../../M15_RUNTIME_PROOF.md) · [M17–M19](../../M17_M19_NATIVE_ID_AND_ITEM_ENUM_STATUS.md) · [M20 反证](../../M20_ITEM983_CACHE_ORIGIN.md) · [[02-Items-And-Native-Kinds]]。

[资源专题索引](README.md)
