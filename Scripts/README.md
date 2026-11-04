# Pokopia 2.0.1 解包工具（M0/M1/M2 首版）

Python 3.10+、仅标准库。默认只读取 `2.0.1/`，所有解析报告写到 `UnPack/` 或 `_meta/`，生成的游戏素材不提交 GitHub。

在仓库根目录运行：

```powershell
# M0：扫描目录和分卷连续性，首次可跳过哈希以快速检查
python -m Scripts.unpack.inventory --source 2.0.1 --output _meta/2.0.1
# 完整校验：耗时和磁盘读取量较大
python -m Scripts.unpack.inventory --source 2.0.1 --output _meta/2.0.1 --hash --test-7z

# 需要先通过现有 .github/workflows/restore.yml 或本地 7-Zip 恢复 .7z.001
# 例如：7z t "2.0.1/romfs/LD_C0_R.BIN.7z.001"
#        7z x "2.0.1/romfs/LD_C0_R.BIN.7z.001" -o_work/2.0.1-restored/romfs

# M1：仅解析索引；这是可在仓库现有 IDX 上直接运行的模式
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --output _meta/2.0.1/linkdata
# 恢复后抽样提取并尝试 zlib；保留 raw，即便解码失败
python -m Scripts.unpack.linkdata --idx 2.0.1/romfs/LI_C0_R.IDX --bin _work/2.0.1-restored/romfs/LD_C0_R.BIN --output UnPack/2.0.1/LINKDATA --start 0 --limit 20 --decode --resume

# M2：支持 root+system；若 FDATA 未还原则报告 CONTAINER_NOT_PRESENT
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output _meta/2.0.1/ktrdb
# 小样本实际提取；先验证再逐步扩大 limit
python -m Scripts.unpack.ktrdb --base _work/2.0.1-restored/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE --output UnPack/2.0.1/KTRDB --extract --decode --limit 20 --resume

# 验证
python -m unittest discover -s tests -v
```

**状态限制：** M1 的 flag=1 目前会尝试标准 zlib，但必须用真实恢复 BIN 验证；任何解码失败都保留 raw 并记录原因。M2 对 `.file` 仅保留完整原始字节，不宣称对其特殊格式已支持语义解析。大型 FDATA 恢复后再做全量测试，当前已验证的是小型真实 KIDSOBJDB 压缩记录。
