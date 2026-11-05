# M20 — 983 描述符、后继包装函数与全局缓存指针溯源

## 原版字节已证实的结论：983 是 OpenSSL NID，不是物品表加载 ID

M20 对原版 NSO0 的 data 描述符和 rodata 字符串指针逐字节解码，确认：

| 原生注册表索引 | 短名称 | 长名称或类型 | 描述符 RVA |
| ---: | --- | --- | --- |
| 982 | `md_gost12_256` | GOST R 34.11-2012 with 256 bit hash | `0x335DE70` |
| **983** | **`md_gost12_512`** | **GOST R 34.11-2012 with 512 bit hash** | **`0x335DE98`** |
| 984 | `id-tc26-signwithdigest` | 加密签名对象标识 | `0x335DEC0` |

这三条原始记录的 `+0x10` 都等于自身编号，`+0x00` 与 `+0x08` 是对应名称/说明的原始字符串指针；`+0x18` 是以原始字节保留的 ASN.1 OID 数据指针。三项名称和数字与 OpenSSL `obj_mac.h` 的 `NID_id_GostR3411_2012_256=982`、`NID_id_GostR3411_2012_512=983`、`NID_id_tc26_signwithdigest=984` 完全一致：

https://github.com/openssl/openssl/blob/master/include/openssl/obj_mac.h

因此此前 M11 的 `mov w0,#983 → 0x1445E30 → 0x14718F0 → global 0x36D54C8` 是**加密对象/NID 查询链**，不应再被列作 LINKDATA `00983.bin` 物品表加载线索。完全独立的两套编号恰好都使用 983，并不说明存在资源引用。

**这次逆向明确排除了错误入口**：以后不得再拿这两个 `983` 相等作为原生物品关系的证据。真正的主路径是 M12/M18 的 `4600-ID -> registry 0xC7 -> vtable+0x30 -> returned object+8 -> +0x26/+0x3A`，其背后原始 68 字节记录身份仍待证明。

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

## 关键待证明连接（改从 M12/M18 物品访问链继续）

```text
原生 4,600-ID 遍历 → registry 0xC7 对象 → 虚表 +0x30 → 返回对象 +8
    → +0x26/+0x39/+0x3A 条件消费者
                      ↑
        仍需追溯的对象/表缓冲区来源
                      ↑
            原始 00983.bin（64 + 4600 × 68）
```

待完成真实类构造/registry 注入、具体虚表方法、返回对象 +8 的内存来源、与 00983.bin 原始 SHA 及多条记录 68 字节逐项一致性验证；静态证据不足时可采用 M15 已实现的只读 GDB 抽样（需要用户真实运行时日志）。

`0x36D54C8` 的精确静态扫描仅有两处已证实 `STR`，其所属 **OpenSSL/NID crypto 路径**不应被误认为物品缓存。尚无经原生证据确认的逐物品最大堆叠数、正式材料分类或持有上限字段。

本报告的详细 JSON 和工作流可以复现这个**否证结果**，不是宣称已找到了 00983.bin 的原生游戏加载器。
