---
title: TEXINFO 108字节单记录真实样本
tags: [pokopia, 2-0-1, samples, hex, texture]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# TEXINFO 单记录：名称、层、UV 与尾字段

**源文件**：
`UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/root_000050_003ad79a.texinfo`

仓库 **Git Blob SHA**：`9e17dadba3ec3599fd1b092dcd0812363101fdd3`（不是文件 SHA-256）；真实文件长度 **108 字节**。

## 原始字节与解读

~~~text
0x00: 01 00 00 00                         记录数 = 1
0x04: 73 74 69 6c 6c 5f 74 75 74 6f 72 69 61 6c 5f 31 32 33 00 ...
      ASCII "still_tutorial_123"，名称字段总宽度 64 字节
0x44: 00 00 00 00                         layer = 0 (u32 little-endian)
0x48: 00 00 00 00                         u0 = 0
0x4C: 00 00 00 00                         v0 = 0
0x50: 01 00 53 3f                         u1 ≈ 0.82421881
0x54: 00 00 00 00                         v0b = 0
0x58: 00 00 00 00                         u0b = 0
0x5C: 00 00 6c 3f                         v1 = 0.921875
0x60: 01 00 53 3f                         u1b ≈ 0.82421881
0x64: 00 00 6c 3f                         v1b = 0.921875
0x68: 01 00 00 00                         未定义尾字段 = 1
~~~

表中 `0x44..0x68` 是 **文件绝对偏移**；若按 TEXINFO 记录相对偏移，则要减去 4 字节的 count 头。UV 的浮点值应保留到导出阶段，不要提前取整。这份单记录仅证明 TEXINFO 结构，**没有给它擅自配对 G1T**。

## PowerShell 检查

~~~powershell
$path = "UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/root_000050_003ad79a.texinfo"
$b = [IO.File]::ReadAllBytes($path)
if ($b.Length -ne 108) { throw "Unexpected TEXINFO size" }
$name = ([Text.Encoding]::ASCII.GetString($b, 4, 64) -split [char]0)[0]
$uv = 0..7 | ForEach-Object { [BitConverter]::ToSingle($b, 0x48 + ($_ * 4)) }
[pscustomobject]@{
  Count=[BitConverter]::ToUInt32($b,0)
  Name=$name
  Layer=[BitConverter]::ToUInt32($b,0x44)
  UV=($uv -join ", ")
  Tail=[BitConverter]::ToUInt32($b,0x68)
}
git hash-object -- $path
~~~

应为 1 条、名称 `still_tutorial_123`、layer 0、上述八个 UV 分量、tail 1；`git hash-object` 应匹配标记的 Git Blob SHA。

对于**已建立索引关联**的主道具图集，另外使用：
[1,333 条 UV 明细](../../../../UnPack/2.0.1/Resources/Textures/Indexes/item_atlas_1333_uv.csv) 和 [主图集导出器](../../../../Scripts/resources/export_native_item_atlas.py)。主图集是 2 层 2048×2048 BC7，采用 `ounce16` 布局裁成 72×72 PNG，须核对 PNG manifest、像素状态和来源哈希；不能把该结论自动赋给本单记录。

参见 [[docs/2.0.1/Technical/Formats/04-TEXINFO-G1T]]。
