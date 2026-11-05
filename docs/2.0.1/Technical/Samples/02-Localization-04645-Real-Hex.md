---
title: 04645.bin 日语物品文本原始字节样本
tags: [pokopia, 2-0-1, samples, hex, localization]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 04645.bin：原生名称表的相对指针

**原始来源**：`UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/04645.bin`，是 LINKDATA 条目 4645，而非文本的剧情 ID。

**SHA-256（原生验证报告）**：`354833598ed4792fddef980538d2d69e069bd29ae3d5eb2e2989634bc6851de3`；文件长度 **174,680 字节**。

## 真实文件头与首条索引

~~~text
0x00  b9 0b 00 00 02 00 00 00
       count = 3001   version = 2
0x08..0x3F  全零（56 字节）
0x40  20 77 01 00 1d 77 01 00 1a 77 01 00 17 77 01 00
0x50  14 77 01 00 11 77 01 00 00 00 00 00 00 00 00 00
~~~

第一指针 `0x00017720 = 96032`，`96032 / 3001 = 32`，因此该文件符合 **32 字节索引宽度**。索引区末端 `64 + 3001 × 32 = 96096`。每条 32 字节含 6 个相对文本指针及 2 个未知原始 u32，不可将 6 个槽预先命名为性别、复数等语言学形式。

第 4 条（零基索引）的索引起点是 `64 + 4 × 32 = 192`；第一个相对指针读得 `0x00017712`，对应的字节绝对偏移是 `192 + 0x17712 = 96210`。文本必须从该位置读取到 NUL，按严格 UTF-8 解码。

## 复现

~~~powershell
$path = "UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/04645.bin"
$b = [IO.File]::ReadAllBytes($path)
$count = [BitConverter]::ToUInt32($b, 0)
$width = [BitConverter]::ToUInt32($b, 64) / $count
$row = 4
$field = [int](64 + $row * $width)
$relative = [BitConverter]::ToUInt32($b, $field)
$absolute = $field + $relative
[pscustomobject]@{ Count=$count; Width=$width; Row=$row; PointerField=$field; Relative=$relative; Absolute=$absolute }
[BitConverter]::ToString($b, $field, [int]$width)
~~~

期待 `Count=3001`、`Width=32`、`PointerField=192`、`Absolute=96210`。随后再使用 [recover_native_text_ids.py](../../../../Scripts/resources/recover_native_text_ids.py) 读取文本与零终止边界。

- 条目 4645–4653 的九语言顺序：jp / en / fr / it / de / es / zht / ko / zhs。
- [原生校验报告](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/validation.json) 的 `MATCH` 只涵盖物品名称，不为剧情/任务文本的外键提供证明。
- 结构测试：[test_m7_localization.py](../../../../tests/test_m7_localization.py)；见 [[docs/2.0.1/Technical/Formats/06-Native-Text-Tables]]。
