---
title: 现有解析器单元测试与实际样本复验
tags: [pokopia, 2-0-1, validation, testing]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# 回归测试命令与验收边界

从仓库根目录执行；请先确认 `python --version` 和依赖安装。以下是**现有测试文件对应的命令**，不是本轮所有测试已通过的声明。

## 合成 fixture / 单元测试

~~~powershell
python -m unittest discover -s tests -p "test_unpack_core.py" -v
python -m unittest discover -s tests -p "test_decode_kidsobjdb.py" -v
python -m unittest discover -s tests -p "test_g1t_to_png.py" -v
python -m unittest discover -s tests -p "test_m7_localization.py" -v
python -m unittest discover -s tests -p "test_audit_native_item_fields.py" -v
python -m unittest discover -s tests -p "test_m3_rdok_sqlite.py" -v
~~~

对应源码：[unpack core](../../../../tests/test_unpack_core.py)、[KIDSOBJDB](../../../../tests/test_decode_kidsobjdb.py)、[G1T](../../../../tests/test_g1t_to_png.py)、[M7](../../../../tests/test_m7_localization.py)、[物品字段](../../../../tests/test_audit_native_item_fields.py)、[M3 SQLite](../../../../tests/test_m3_rdok_sqlite.py)。

注意：合成 fixture 成功只说明解析器的**被测分支**没有退化，不代表所有游戏资源都可解包。

## 已提交真实文件复验（不会修改原文件）

~~~powershell
$dir = "UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded"
$item = Join-Path $dir "00983.bin"
$text = Join-Path $dir "04645.bin"
if ((Get-Item $item).Length -ne 312864) { throw "00983 length mismatch" }
if ((Get-Item $text).Length -ne 174680) { throw "04645 length mismatch" }
if ([BitConverter]::ToUInt32([IO.File]::ReadAllBytes($item), 0) -ne 4600) { throw "item count mismatch" }
if ([BitConverter]::ToUInt32([IO.File]::ReadAllBytes($text), 0) -ne 3001) { throw "text count mismatch" }
(Get-FileHash $item -Algorithm SHA256).Hash.ToLowerInvariant()
(Get-FileHash $text -Algorithm SHA256).Hash.ToLowerInvariant()
~~~

期待 00983 SHA-256：`2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`；04645 SHA-256：`354833598ed4792fddef980538d2d69e069bd29ae3d5eb2e2989634bc6851de3`。哈希依据已提交原生物品 [validation.json](../../../../UnPack/2.0.1/Resources/Items/Native_2.0.1/validation.json)。

## 原生导出验证（有依赖、可能改写导出目录）

默认脚本可能重建 manifest 或覆盖派生的 CSV/PNG；应先把输出目录指向 `_work/` 或使用临时工作副本：

~~~powershell
python -m Scripts.resources.recover_native_text_ids --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded --dest _work/m7-verification
python -m Scripts.resources.export_native_item_atlas --help
python -m Scripts.resources.verify_native_items --help
~~~

执行真实图片/文字完整重建之前，确保 Pillow 等依赖齐全，并记录 `git status --short` 及旧产物备份。不是所有工具都接受 `--dest`；以脚本 `--help` 为准。

## 记录每次跑测

~~~text
test_date:
git_commit:
python_version:
dependencies:
test_command:
pass_count:
fail_count:
skipped_count:
real_source_sha256:
output_sha256:
unresolved_errors:
~~~

本轮文档依据 GitHub 源码、已提交 JSON 和实际读取的三个二进制样本；**没有执行以上全套测试，因此不填写虚假的 PASS 数量**。
