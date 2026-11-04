# Git 原生后缀目录别名（零重传二进制）

为 `UnPack/2.0.1/romfs/.../<原始源文件名>/` 中已确认 RDB 原始类型的 **79,714 条资源**创建 `native/` 目录。

示例：
```text
UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x4b13d561.fdata/
├── decoded/root_010349_2af82b77.fdata_idrk.bin
├── native/root_010349_2af82b77.kidsobjdb
└── _manifest.csv
```

**Git 的两个路径指向同一个 blob SHA。** 这只是树对象中增加文件名引用，不会对已经提交的 18GB 二进制重复生成 Git blob，也不会对 SHA-256 尚未验证的文件重命名或猜测内容。

- 扩展名来自 `m3_resource_type_index.csv`，保存 `extension_evidence`；只有标记 `MAGIC_AND_TKID` 的有内容头部与哈希双重确认，其余 `EXTERNAL_TKID_INFERRED` 只是跨游戏映射假设。
- 单文件记录直接以 `.g1m/.g1t/.g1a/.g1s/.kidsobjdb/...` 展示；分段大文件用 `.<ext>.part0001`，不能把任何一个 part 误当成完整模型。
- 原始 `decoded/`、`raw/`、`_manifest.csv` 不改变。原先的 M2 路径/大小核验仍可继续使用。
- `native_aliases.csv` 记录每一条的源路径、目标路径、SHA-256 及证据等级。
- 必须运行 `Scripts/unpack/export_native.py` 才能把大文件的多个 part 拼成单个原生文件并进行重组 SHA-256 校验。
- `.g1t` 仅是 KT 引擎原生纹理容器，未自动变成 PNG；`.g1m` 也尚未变成 glTF。
