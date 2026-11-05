---
title: M7九语言记录真实来源追踪
tags: [pokopia, 2-0-1, samples, localization, evidence]
game_version: "2.0.1"
status: PARTIAL
updated: 2026-11-05
---

# M7：一条九语言文本的证据链

该案例不是“通过关键词猜剧情”，而是引用仓库内 [M7 原生样本记录](../../../../UnPack/2.0.1/Resources/Localization/M7/Samples/native_02350_record_00004.json)。

| 属性 | 文件里实际记录的值 |
| --- | --- |
| 分组 | LINKDATA 02350–02358 |
| 零基记录号 | 4 |
| 单语言表记录数 | 248 |
| 单条索引宽度 | 8 bytes |
| 日语 | 02350.bin；字符串绝对偏移 2314；原始 flags = 1 |
| 英语 | 02351.bin；字符串绝对偏移 2201；原始 flags = 1 |
| 简体中文 | 02358.bin；字符串绝对偏移 2221；原始 flags = 1 |
| 脚本/场景引用 | `UNVERIFIED` |
| 已赋游戏类别 | `UNKNOWN` |

文本包含 `<$voicel(...)>`、`<$motionoff(...)>`、`<br>` 等原生控制标签。这些标签不得用简单正则清理后当成无损转换；原始字节偏移与 UTF-8 字符偏移不能混用。样本的 `blob_sha1` 是源文件 SHA-1，不是 SHA-256。

## 如何重现并检查

~~~powershell
python -m unittest discover -s tests -p "test_m7_localization.py" -v
python -m Scripts.resources.recover_native_text_ids --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded --dest _work/m7-rebuild
$record = Get-Content UnPack/2.0.1/Resources/Localization/M7/Samples/native_02350_record_00004.json -Raw | ConvertFrom-Json
$record.source_entries.jp | Format-List
$record.source_entries.en | Format-List
$record.source_entries.zhs | Format-List
~~~

将新结果中的 `entry`、`record_id`、`absolute_byte_offset`、`flags_raw_u32` 与仓库样本对账；控制标签中的文本可能包含私有字形码位，读取必须严格保留 Unicode 原值。

**证据等级**：九语言表结构对齐、原生索引与字符串存在已成立；但 **“某个任务/场景实际调用这条文本”没有原生消费者调用链证明**。这是另一个待完成的研究目标，不得由语义上像对话便补写游戏剧情外键。

相关：[[docs/2.0.1/Technical/Formats/06-Native-Text-Tables]] · [M7 报告](../../../../UnPack/2.0.1/Resources/Localization/M7/m7_report.json)。
