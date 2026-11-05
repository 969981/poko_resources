# Pokopia 2.0.1 — Localization / 原生语言文本定位

**状态：物品名称九语言已核验；剧情、UI、教程、任务及其他字符串仍在候选定位阶段。** 不得将本目录的候选扫描结果当作完整游戏翻译库。

## 已确认的原生位置

相对于仓库根目录：

- 物品数据表：`UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin`（4,600 槽）
- 语言文本表：同一 `decoded/` 目录中的 `04645.bin` 至 `04653.bin`。
- 验证清单：`UnPack/2.0.1/Resources/Items/Native_2.0.1/validation.json`。此前九语言对照均 MATCH，差异 0；校验范围**仅道具名称**。
- 已有九语言可检索文本：`UnPack/2.0.1/Resources/Items/Text/text_item_<lang>.txt`；物品 ID 为零基行号，不能删空行或重排。
- 其他参考文本：`Resources/Villagers/Text/`、`Resources/Reactions/Text/` 和 `Resources/Skills/Text/`，当前来自固定版本 PokoHex，并非已核验的 2.0.1 原生表。

| 语言 | 条目编号 | 原始文件 |
|---|---:|---|
| 日文 jp | 4645 | 04645.bin |
| 英文 en | 4646 | 04646.bin |
| 法文 fr | 4647 | 04647.bin |
| 意大利文 it | 4648 | 04648.bin |
| 德文 de | 4649 | 04649.bin |
| 西班牙文 es | 4650 | 04650.bin |
| 繁体中文 zht | 4651 | 04651.bin |
| 韩文 ko | 4652 | 04652.bin |
| 简体中文 zhs | 4653 | 04653.bin |

对应 Hash 和原始文件完整性检查请以 validation.json 为准。

## 剧情 / 菜单字符串的下一步定位

社区 PT-BR 项目 `ProfMPPDias/pokopia_ptbr_mdias` 的 `scripts/extract_texts.py` 在 `LI_C0_R.IDX` / `LD_C0_R.BIN` 中搜寻 `<$`、`<oneline>` 等控制标签；其 `build_perfect_v3.py` 引用了 2324、2351、3305 等条目。这些编号是**第三方脚本所引用的候选条目**，不是本仓库已经独立逐字节验证的原生语言表，更不应误将英语文本代表九语言。

本仓库新增只读扫描工具：

```bash
python3 Scripts/resources/discover_native_text.py \
  --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded \
  --dest UnPack/2.0.1/Resources/Localization

# 优先采样第三方所引用的候选条目
python3 Scripts/resources/discover_native_text.py \
  --decoded-root UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded \
  --entries 2324 2351 3305 \
  --dest UnPack/2.0.1/Resources/Localization/Samples
```

运行后生成 `source_files.csv`、`text_candidates.csv`、`discovery_report.json`。CSV 保留 LINKDATA 条目编号、解包文件路径、SHA-256、解包文件内偏移、原始带控制符文本。候选不会被认作已确认的语种、完整字符串表或游戏展示文案。

## 验收标准

1. 从真实 2.0.1 原生条目中恢复字段、文本分段及标签，而不只是字符串扫描。
2. 将同一文本 ID 的各语言与语言选择表建立可复现的引用关系，输出九语言 CSV/JSON。
3. 对不同类别分别归档：剧情 Dialogue、菜单 UI、任务 Quest、物品 Items、建筑 Buildings、教程 Tutorials。
4. 输出索引 `resource_hash → decoded_entry → byte_offset → text_id → language → category`，每条保留证据等级；不能验证的字段留空。
5. 对照实体游戏/运行时或已知参考数据采样确认，验证控制符、空槽位及多语言一致性。

原始资料保持在 `UnPack/2.0.1/romfs/`，本目录只放衍生索引和经过验收的文本。现阶段没有声称已完成全游戏九语言提取。

## 新增：实际 UTF-8 TXT / JSONL 发布

M7 四组九语言原生锚点已经通过 `.github/workflows/unpack-m7-text-export.yml` 导出并经 SHA 校验。输出位于 `Resources/Localization/TextExports/`：`table_02323`（515 条）、`table_02350`（248 条）、`table_03304`（10 条）、`table_04645`（3001 条，6 个原生 form）。每组九个 TXT 和九个无损 forms.jsonl，同时保留 manifest.json 和总报告。脚本 `Scripts/resources/export_native_text_files.py --all-groups` 可以明确选择全部 195 个 M7 候选组，但未运行的部分不得声称已发布。分类仍以原生引用证据为准。
