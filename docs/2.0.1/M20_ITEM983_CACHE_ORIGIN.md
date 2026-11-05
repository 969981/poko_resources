# M20 — 983 描述符、后继包装函数与全局缓存指针溯源

## 研究范围

从 M11 已经核对的 `main+0x14FD9B0 / +0x14FDB1C` 开始，追踪 `main+0x1445E30`、`main+0x14718F0` 后继和全局 `0x36D54C8`；与 M12/M18 已确认的 4,600-ID 虚函数物品读取路径并列核对。

**不以数字 983 的相等、字段 +0x26 相等、40 字节描述符和 68 字节原始记录的近邻来推导未证实的结构身份。**

## 原始资料与严格边界

- `2.0.1/exefs/main`：SHA-256 `8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f`。
- `UnPack/2.0.1/romfs/LD_C0_R.BIN/decoded/00983.bin`：SHA-256 `2a2dbc88715dc76410cef495d418613456c0c4fa7b7d719e7b37709ad53e1b6f`；原始 `64 + 4600*68` 字节。
- NSO text RVA 是原生模块相对偏移，不是压缩文件偏移，也不是运行中的绝对 PC。

## M20 新增可复现步骤

```bash
python -m unittest discover -s tests -p "test_m20_item983_cache_provenance.py" -v
python -m Scripts.resources.m20_item983_cache_provenance
```

`Scripts/resources/m20_item983_cache_provenance.py`：

1. 在原版 NSO rodata/data 中定位并读取 `0x3354500 + 983 * 0x28` 的 **40 字节描述符原文**，记录 10 个小端 u32、物理 NSO 虚拟地址和 SHA；同时取 0/982/984/1194 作为负对照及邻接证据，验证 ID 允许范围。
2. 扫描 1,195 个描述符的原始词，看是否出现 `4600`、`68` 和原始文件大小 `64+4600*68`，但即使出现也只视为线索。
3. 严格核验两条 `mov w0,#983 → BL 0x1445E30 → BL 0x14718F0 → STR x0 → global RVA 0x36D54C8` 的机器指令。
4. 反汇编 `0x14718F0`、其后继 `0x1471990`、`0x1444210` 及 ID 入口；扫描所有直接 `BL` 调用者。
5. 在整段 NSO text 扫描 `ADRP 0x36D5000`，向后做有限、可见、基本块内的 `ADD/SUB` 地址寄存器传播，只把访问到确切 RVA `0x36D54C8` 的 `LDR/STR/LDUR/STUR` 标为**原生直接全局访问**。不把任意 `[xN,#0x4C8]` 当作这个全局，也不把未找到直接 `LDR` 当成全局未使用的证明。
6. 独立重新验证 M12/M18 4,600-ID 遍历和虚表 `+0x30`、返回对象 `+8`、读取 `+0x26/+0x3A` 的原始指令位置。

原始全部输出：

- `UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M20/m20_native_983_cache_provenance.json`
- `UnPack/2.0.1/Resources/Items/Native_2.0.1/ExeFS/M20/m20_native_983_cache_summary.json`

CI：`.github/workflows/unpack-m20-item983-cache-provenance.yml`；产物归档到 GitHub Actions，无原版 ExeFS/ROM/其他大型资源写回提交。

## 关键待证明连接

目前有**两条独立且有原生指令来源的路径**：

```text
983 -> 40-byte descriptor lookup -> 0x14718F0 -> global 0x36D54C8
4600 item-like ID sweep -> registry 0xC7 -> vtable +0x30 -> object +8 -> +0x26/+0x3A
```

中间仍需完成：

- 查清 `0x14718F0` 返回对象的结构及实参对象指针来源；
- 确认缓存全局 `0x36D54C8` 是否通过其它指针别名或间接对象读法进入 `0xC7` 注册对象；
- 从 `0xC7` 具体类的构造、注册动作，确定真实 `vtable+0x30` 实现；
- 证明实现加载或映射 **原始 `00983.bin` 全部 4,600 项**，且原生记录地址可解释为 `64 + ItemID*68`（或有可复现的转换映射），再验证具体字段比较的游戏含义；
- 保存时单组最大数量、背包总容量、正常玩法约 99、存档 `uint8` 0–255 **互不等同**。

只有跨组件实际指针来源闭合后才能将材料枚举、逐项最大堆叠和持有数量限制标记为已验证。静态数字/布局一致或某字段被比较，不足以升格。
