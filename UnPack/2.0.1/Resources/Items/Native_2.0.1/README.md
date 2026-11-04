# Pokopia 2.0.1 原生道具文本核验

该目录用于 **直接从当前 2.0.1 解包的 LINKDATA 原始条目** 校验 PokoHex 九语言道具名称，而不是仅复制第三方数据。

原始路径：`UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/`。

- `00983.bin`：物品表，4600 个 ID 槽位，版本 3、记录大小 68、名称索引偏移 +34。
- `04645.bin`～`04653.bin`：9 种语言名称表。按 PokoHex `GameItemDumper.cs` 的新版 LINKDATA 映射恢复。
- 对照库：`Resources/Items/Text/text_item_{en,jp,de,es,fr,it,ko,zhs,zht}.txt`。
- 校验目标：逐 ID 输出原生文字、差异 CSV、原始 SHA-256 与语言匹配率。

**不能由物品名称直接认定素材类别，也不能将 G1T Hash 误作游戏物品 ID。** 纹理身份需进一步结合资源引用/KIDSOBJDB/KTID 证据。
