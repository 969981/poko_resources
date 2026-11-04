# 目录与 Git 提交约定

```text
poko_resources/
├── 2.0.1/                           # 历史原始输入，不变
│   ├── exefs/main                    # 必须保留
│   └── romfs/
│       ├── LI_C0_R.IDX
│       ├── LD_C0_R.BIN.7z.001 ...
│       └── motor_asset_re/KIDS_PLATFORM_OUNCE/
│           ├── root.rdb / root.rdx
│           ├── system.rdb / system.rdx
│           ├── *.fdata(.7z.NNN)
│           ├── data/*.file(.7z.NNN)
│           └── MountPoint_1 / MountPoint_2
├── Scripts/
│   ├── inventory/                    # 清单、卷检测、恢复核对
│   ├── linkdata/                     # IDX/BIN 索引及提取
│   ├── ktrdb/                        # RDB/RDX/FDATA/file
│   ├── formats/                      # KIDSOBJDB/BFBS/texture/model
│   └── verify/                       # 证据、哈希、回归
├── UnPack/2.0.1/
│   ├── LINKDATA/raw/                 # 大文件，本地生成，不提交
│   ├── LINKDATA/decoded/
│   ├── KTRDB/raw/
│   ├── KTRDB/decoded/
│   ├── Converted/Database/
│   ├── Converted/Text/
│   ├── Converted/Texture/
│   ├── Converted/Model/
│   └── Converted/Scene/
├── _meta/2.0.1/                      # manifest/SQLite/CSV/错误统计
├── _work/2.0.1-restored/             # 临时恢复与缓存，禁止提交
├── docs/2.0.1/                       # 技术规划、证据与进度
└── tests/                            # 小型合成 fixture 与测试
```

Git 不能追踪空目录；各目录将在有首个代码或报告时自然出现。本次提交包含 `Scripts/README.md`、`UnPack/2.0.1/README.md` 和 `_meta/2.0.1/README.md` 作为入口。

**严禁**在一般提交中加入整个 `UnPack`、`_work`、临时恢复的 `LD_C0_R.BIN` 或其他游戏二进制。已追踪的 `2.0.1/` 原始数据不受 .gitignore 影响，也不要求删除。

命名：`{source_kind}_{id_or_hash}_{record_no}.{raw_extension}`，稳定的 ID 和原始记录编号优先；如遇同名冲突，不可静默覆盖。

每个输出元数据最少包含：`source_path`、`source_sha256`、`index_name`、`record_id`、`offset`、`packed_size`、`unpacked_size`、`flags`、`codec`、`output_sha256`、`status`、`error`、`tool_version`。
