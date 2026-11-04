# Pokopia 2.0.1 Resources — 道具、图标、多语言与纹理线索

此目录是 **从 `UnPack/2.0.1/romfs/` 中间层衍生出的可用资源索引**；原始、逐条解包内容继续保留在 `romfs/` 下，不做重排覆盖。当前分两套来源：

1. **PokoHex 已整理资源（可直接按道具 ID 使用）**：源仓库 [969981/PokoHex](https://github.com/969981/PokoHex)，固定提交 `c71d2b73fb9d8cfe99c1067e6bfadfd19f60bf78`；9 语言名称文本和 `MenuIcon/item_*.png` 物品 PNG。它们是 PokoHex 资源，**暂未证明每个文件都来自当前 2.0.1 游戏镜像**。
2. **本仓库 2.0.1 原始解包证据**：`_reports/m3_resource_type_index.csv` 中带 `.g1t` 扩展名推断的资源；其 ID 与游戏道具 ID **尚未建立直接映射**，不可把文件名 Hash 当作道具 ID。

## 目录与产物

```text
UnPack/2.0.1/
├── romfs/                                  # 已有原始路径镜像，不改变
└── Resources/
    ├── README.md
    ├── SOURCE_AND_COVERAGE.json           # 运行后生成，记录数量、来源和限制
    ├── Items/
    │   ├── Text/text_item_{en,jp,de,es,fr,it,ko,zhs,zht}.txt  # 4600 行；行号等于 ID
    │   ├── Icons/item_0006.png ...        # PokoHex 中真实存在的图标
    │   ├── item_catalog.csv               # 按 ID 联合 9 语言 + 图标 + menuicon 原始值
    │   └── missing_pokohex_icons.csv      # 有名称但 PokoHex 没有 PNG 的 ID
    └── Textures/
        └── g1t_candidates.csv             # RDB→原始目录→解包产物，待格式解析
```

文本每行的 **0 起始行号**对应 `item_id`，不得删除空行或按名称排序。PokoHex 当前 9 语言各 4600 槽、3586 个非空名称；PokoHex 图标文件 1615 张。页面和修改器统一使用 `item_id` 连接；一旦发现同名多 ID，不做自动合并。对外提供图片前请留意游戏素材的著作权和项目原有许可证。

`pokohex_menuicon_raw_u16` 为 PokoHex `item_menuicon.bin` 的原始 16-bit 表值，**不能未经验证就视为纹理偏移或 RDB 记录 ID**。

## 自动重建

`.github/workflows/build-resources.yml` 支持手动运行；此分支第一次提交脚本时也会触发。它会检出固定 PokoHex 提交，复制原有 PNG、文本，并用现有 M3 类型索引生成 CSV 和统计报告，然后提交到 `2.0.1_unpack`。

本地执行：

```bash
python3 Scripts/resources/import_pokohex.py \
  --source /path/to/PokoHex \
  --dest UnPack/2.0.1/Resources \
  --m3-index UnPack/2.0.1/_reports/m3_resource_type_index.csv
```

## 还未完成

- 对缺失 PNG 的条目，从原始 `.g1t` 解析纹理容器并导出图像，再从 KIDSOBJDB/KTID/命名及引用关系匹配道具 ID。
- 在 2.0.1 的 `LD_C0_R.BIN` 解包条目上重新验证 **物品表索引 983** 及各语言名称索引（PokoHex 的 v3 分支提供索引算法）；保留 Hash 和字段级来源。
- 当前只整理“道具名称”九语；后续可扩展 `villager/area/skill/reaction`。不要把未解析资源误报为已完成。

**来源范围说明：** 用户提供的离线下单页面是一份二次筛选目录，其 2611 个产品不等于游戏 4600 槽位、3586 个有名称条目或 PokoHex 的 1615 张 PNG。分类、叠加数量和商品可选性不能自动推定为 2.0.1 游戏原始字段。


## M5 — 2.0.1 RomFS G1T 纹理候选解码

已新增 Scripts/resources/g1t_to_png.py 和 .github/workflows/unpack-m5-textures.yml。
与 PokoHex 图标导入是两条独立证据链，不能因为 PokoHex 有 PNG 就声称来自原始 2.0.1 RomFS。

- 已从真实 G1T 解析 GT1G0600、平台字段 0x18、格式 0x66 (BC7) 和 0x62 (BC3/DXT5)。
- 提取阶段分别测试 linear、gob1、gob2 三套排列，用 Pillow 转成真正的 PNG。
- 输出：Textures/Previews/ 和 Textures/texture_manifest.csv；状态 DECODED_UNVERIFIED 只代表 PNG 解码通过，不代表画面内容正确。
- 原生 TEXINFO 纹理名输出到 Textures/texinfo_names.csv；item_XXXX_m 仅作为候选 ID；尚无可证明 TEXINFO 精确指向哪条 G1T 的完整链。
- 全量 M3 的 14,412 条 G1T 推断记录位于 Textures/g1t_candidates.csv，这不是 PNG 成功总数。
- 保留原始 G1T、原始 TEXINFO 路径及每个候选 PNG 的 SHA-256；暂不覆盖 PokoHex 正式道具图标。

本地复现需要 Python 3.10+、Pillow 11+，可运行：
    python -m pip install "Pillow>=11,<13"
    python -m unittest discover -s tests -p "test_g1t_to_png.py" -v
    python Scripts/resources/g1t_to_png.py --input UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/root_000333_016719f3.g1t --texinfo-root UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native

验收：视觉确认排列和 Alpha 后，再利用 RDB/KTID/对象引用建立 TEXINFO → G1T → 物品 ID 的直接对应。不能仅用名称中相同的数字或 RDB 邻近记录自动匹配。
