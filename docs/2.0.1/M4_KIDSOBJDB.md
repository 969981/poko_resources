# M4 KIDSOBJDB 结构解析（实验性）

输入为 `UnPack/2.0.1/.../decoded/` 中已验证的二进制负载，**不更改原始解码产物**。

`Scripts/unpack/decode_kidsobjdb.py` 验证 `_DOK0000` 主头、IDOK/RDOK 子块边界与大小，读取 IDOK 属性名哈希/类型哈希与定长数值字段。

当前仅支持 `type_code` = 0, 1, 2, 3, 4, 5, 8, 10, 12, 13 的定长字段，限制采样数，完整文件哈希留存。所有 RDOK 与其他字段类型均明确标记为 `RDOK_OPAQUE` / `UNSUPPORTED_TYPE`，**不能算已完整语义解包**。

运行：
```powershell
python -m Scripts.unpack.decode_kidsobjdb --input path/to/file.kidsobjdb --output result.json
```

本仓库 Actions 通过真实 96 字节样本测试结构与安全检查，输出 `UnPack/2.0.1/_reports/m4_kidsobjdb_root_010349.json`。后续应扩大到全部 4,144 条 KIDSOBJDB、补齐 RDOK 结构及实际命名关联。
