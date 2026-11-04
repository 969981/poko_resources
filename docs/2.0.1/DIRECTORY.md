# Pokopia 2.0.1 解包路径和提交规则

### 原始数据（保持不变）
```text
2.0.1/
  exefs/main
  romfs/
    LI_C0_R.IDX
    LD_C0_R.BIN.7z.001/.002
    motor_asset_re/KIDS_PLATFORM_OUNCE/
      root.rdb / root.rdx
      system.rdb / system.rdx
      0x<hash>.fdata(.7z.001...)
      MountPoint_1/0x<hash>.fdata
      MountPoint_2/0x<hash>.fdata(.7z.001...)
      data/0x<hash>.file(.7z.001...)
```

### 发布目录（已经启用）
```text
UnPack/2.0.1/
  romfs/
    LD_C0_R.BIN/
      decoded/<index>.bin
      _manifest.csv
    motor_asset_re/KIDS_PLATFORM_OUNCE/
      0x4b13d561.fdata/
        decoded/root_<index>_<hash>.fdata_idrk.bin
        _manifest.csv
      0x38f972af.fdata/
        decoded/<record>.bin[.partNNNN]
      MountPoint_1/0x00176283.fdata/
      MountPoint_2/0xc884bce7.fdata/
      data/0x0b5db05b.file/
  _reports/<run>.json
```

**规则：**
1. 一律保留 `2.0.1/romfs` 下面的相对父目录；用**恢复后的完整源文件名（含扩展名）**作为目录。
2. `.7z.001/.002...` 是同一个源容器的分卷，不单独建立目录。
3. 输出内容优先使用 `decoded/`，仅需留存无法成功解码的原始片段时使用 `raw/`；两者不得混为一谈。
4. 已恢复的大容器以及 `_work/` 不进入提交；`UnPack/2.0.1/romfs/` 的逐条产物和追溯元数据进入 `2.0.1_unpack` 分支。
5. 每条记录必须能回溯到源路径、源哈希、记录号、原始偏移、原/解码长度、解码状态、输出哈希。
6. GitHub 不接受大于 100 MiB 的单文件；分段文件使用 `.part0001...` 并在清单中列出顺序。批次预算内未上传的记录统一标注 `SKIPPED_BATCH_BUDGET`，不宣称完成。
7. 禁止覆盖 `2.0.1/` 原始数据，排除 `romfs/movie_asset/`。

相关脚本：`Scripts/unpack/publish.py` 与 `Scripts/unpack/publish_stream.py`。独立 `.file` 的语义解包仍需单独验证。
