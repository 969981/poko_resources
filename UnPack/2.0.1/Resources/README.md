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


## M5.1 — 原生多记录 TEXINFO 图集与双层 G1T（2026-11-05）

**新增已验证的结构证据（来自 2.0.1 原始解包字节，不是从 PokoHex 猜测）：**

- 文件 `romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/root_042753_b4b1fe49.texinfo` 长度 **138,636 字节**，头部小端 `u32=1333`；满足 `4 + 1333 × 104` 的真实多记录结构。
- 每条记录：64 字节 ASCII sprite name、一个原始 `u32` 层/页标识、8 个 `float32` UV 顶点和尾部 `u32`。目前已核对 `item_0006` 等真实名称及坐标。
- 1,333 条记录的 `texture_layer_raw_u32` 分布是 **层 0: 727 条、层 1: 606 条**。这里的“层”是对原始字段的描述；G1T 内实际纹理数组/多图块排布还需要读取容器头和解码验证。
- `item-texture-map.tsv` 和 `layout-textures.tsv` 的对应证据指向 `b4b1fe49.texinfo → a0ce9914.g1t`；后者原始资源路径 `root_038147_a0ce9914.g1t`，大小 **8,388,684 字节**。这些是 **索引关系**，并不等同于像素级已经验证正确。
- 另外此前 `texinfo_names.csv` 中 28 个 `UNPARSED` 条目都是可疑的多记录 TEXINFO 文件：过去 `u32 == 1` 的假设过窄。新的解析器改为 `u32 record_count + record_count × 104` 校验和逐条输出；是否所有文件都能通过仍以工作流结果为准。

**已经直接提交的映射：**

`Textures/Indexes/item_atlas_1333_uv.csv` 包含 1,333 个原始 sprite 名、真实 TEXINFO 记录编号、四个 UV 边界、原始层字段、G1T Hash 与 KIDSOBJDB 索引来源。可据此按道具 ID 定位图集子区域。

**新的执行入口：**

- `Scripts/resources/g1t_to_png.py` 的 `parse_texinfo()` / `texinfo_index()` 现支持多记录 TEXINFO。
- `Scripts/resources/link_item_textures.py` 将 TEXINFO 名称与 `item-texture-map.tsv`、`layout-textures.tsv` 按 Hash/名称交叉核对，并输出 `Textures/Indexes/item_native_texture_links.csv` 及 `item_native_texture_audit.json`（待相关工作流生成）。
- `.github/workflows/unpack-m5-textures.yml` 负责重建完整 TEXINFO 索引和交叉核对，包含新的单元测试。
- `Scripts/resources/crop_native_item_atlas.py` 使用 **原始层字段 + UV 坐标** 裁剪 G1T PNG 候选图；严格检查每层 BC 字节长度，不能确定层/MIP 结构时直接报错，不会默默错位。
- `.github/workflows/unpack-m5-atlas-crop.yml` 单独提取少量样本的 linear/GOB 排列、V 轴上下方向候选，上传到 Actions Artifact 供肉眼对比；**不会覆盖** `Items/Icons/` 目录。

**界限：** PokoHex PNG 是直接可用的第三方来源；原生 G1T 的 swizzle、图集层、坐标方向、色彩与 Alpha 都需要与真实画面对照，不能将仅 PNG 解码成功标为原版还原完成。缺失的 2,041 个 PokoHex PNG 条目也不能自动推断为游戏中没有图标。

## 原生九语言核验结论

`Items/Native_2.0.1/validation.json` 记录了以 `00983.bin` 的 4,600 槽物品表与九份 `04645.bin`～`04653.bin` 原生名称表核对的结果：`status=MATCH`、`differences=0`，九种语言均为 4,600 / 4,600 槽一致。文本来源校验已完成，但此结果不包含对道具图像的视觉验证。

## PokoHex 补充资源：宝可梦、反应、技能

新增 Villagers、Reactions、Skills 三组第三方参考资源（9 种语言）。输入来自 969981/PokoHex 的固定提交 c71d2b73fb9d8cfe99c1067e6bfadfd19f60bf78。

- Villagers/Icons：378 张 villager_XXXX.png，XXXX 是肖像 ID，不是游戏 villager ID。使用 villager_portrait.bin 的小端 u16 映射；Villagers/villager_catalog.csv 保存游戏 ID、九语言、肖像 ID 和图标路径。
- Reactions/Icons：47 张 reaction_XXXX.png，Reactions/reaction_catalog.csv 保存九语言、公开状态与 ID 对照；PokoHex 公开规则为 1–100 且英文名称非空。
- Skills/Icons：10 张 skill_XXXX.png，Skills/skill_catalog.csv 保存九语言、公开状态、轮盘能力与图标；公开编号为 1–6、10–13，轮盘为 1–6、12、13。

每类包括 Text/（九语言原始 ID 顺序）、pokohex_icon_sources.csv（原路径和 SHA-256）、missing_pokohex_icons.csv；SOURCE_AND_COVERAGE.json 记录各类统计。源头为 PokoHex 的参考素材，不声明已经从 2.0.1 原版 RomFS 逐张提取或验证像素一致性。

复现命令：

    python3 Scripts/resources/import_pokohex_extra.py --source /path/to/PokoHex --dest UnPack/2.0.1/Resources

完整导入由 .github/workflows/build-resources.yml 执行。未来再通过原生 TEXINFO/G1T/RDB/KTID 引用对账。保留同名不同 ID、同肖像多 ID 的原始关系，不擅自归并。
