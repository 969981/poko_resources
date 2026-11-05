# M27 — 原始 KIDS 图标索引的 31 多项式与倒序四位数字模型

> Pokopia **2.0.1** · Git 分支 \`2.0.1_unpack\` · 原始二进制来源 \`root_019167_50ae86ef.kidsobjdb\`（SHA256 \`86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541\`）。  
> 证据分级：**原始字节 + 独立数值留出集精确校验**，目前仍**不是** ExeFS 实际算法或游戏物种 ID 消费者证明。

关联：[[M26_VILLAGER_ROSTER_AND_KIDS_PARALLEL_ARRAYS]] · [[M25_NATIVE_POKEMON_ICON_REGISTRY]] · [[M23_FDATA_PLATFORM_AND_KIDS_CONSUMER]]。

## 1. M26 实测原始双数组

类型 Hash \`0x9D1AFA46\`、原生对象 Source OID \`0xB4A1803B\` 的属性：

| 原生属性 Hash | 原始二进制字节偏移 | u32 数量 | 对账 |
| --- | ---: | ---: | --- |
| \`0xE88C8D60\` | 364556 | 3,543 | 完整键数组，尚无语义函数证明 |
| \`0x34CBB458\` | 378728 | 3,543 | Source OID 数组，其中 628 条已通过 M25 原始资源边验证 |

原始类中 \`main+0xDD1B48\` 的属性描述器确实返回上述两个 Hash（M26.3），但该函数本身并未证明应用怎样构建、比较、查询字符串 Hash。

## 2. 数值差分精确满足 31 的幂

对常规 \`icon_poke_0000\` 至 \`icon_poke_0009\`，这两个原生数组相邻项差值分别为：

\`\`\`text
key  差值：0x59DB6A41 = (31^14) mod 2^32
OID  差值：0x38E0609F = (31^69) mod 2^32

uni key 差值：0xCDAA61C1 = (31^18) mod 2^32
uni OID 差值：0x1A70F91F = (31^73) mod 2^32
\`\`\`

\`uni\` 各指数比 \`normal\` 多 4。与 31 多项式散列一致，但**无法仅凭相等的差分证明原生函数算法就是该式**。

### 可重复计算的模型

令 \`D\` 为 **TEXINFO 文件名中的四位数字**，而不是游戏真实宝可梦 ID。

\`\`\`python
MASK = 0xFFFFFFFF
def hash31(data: str) -> int:
    v = 0
    for char in data.encode("ascii"):
        v = (v * 31 + char) & MASK
    return v

def predict(four_digit: str, family: str, variant: str, constants: dict):
    x = hash31(four_digit[::-1])
    p_key, p_oid = (11, 66) if family == "normal" else (15, 70)
    ck, cv = constants[(family, variant)]
    return ((x * pow(31, p_key, 1 << 32) + ck) & MASK,
            (x * pow(31, p_oid, 1 << 32) + cv) & MASK)
\`\`\`

**重要：反转的是字符串的 4 个字符（包括前导 0），不是把十进制整数的数值倒转。** 如 \`0043\` → \`3400\`；不要将 \`0043\` 当成已验证的游戏物种编号。

### 两个常规图标族的模型常量

| 原生纹理名称族 | 第一个数组 C（key） | 第二个数组 C（Source OID） | 数字的幂指数 |
| --- | --- | --- | --- |
| \`icon_poke_NNNN_00_00_00\` | \`0x54FAD2C1\` | \`0x2480987E\` | 11 / 66 |
| \`icon_poke_uni_NNNN_00_00_00\` | \`0x21A9BA70\` | \`0xBED90FEF\` | 15 / 70 |

例：原始纹理名 \`icon_poke_0043_00_00_00\`：

\`\`\`text
NNNN                              = "0043"
reverse(NNNN)                     = "3400"
hash31("3400")                    = 0x0017F821
key  = hash31("3400")*31^11+Ckey = 0x469E2C00
OID  = hash31("3400")*31^66+Coid = 0x06AB845F
\`\`\`

最终与原始 KIDS 3543-u32 数组 \`slot=455\` 中的两个值**同时**一致；该 Source OID 已由 M25 的原始 \`0x2856A1B3\` 字段连接到真实 Texture OID 与 G1T/TEXINFO。

## 3. 全部已命名图标：626 项的原始字节验证

从 628 个原生主数组 Source OID 中：

- 626 项名称符合数字格式 \`icon_poke[_uni]_NNNN_FF_FF_FF[_nh]\`。
- 其余两项是 \`icon_poke_blank\`（slot 742）和 \`icon_poke_uni_hatena\`（slot 1056）：没有四位数字，**不允许套用数值模型**。
- 626 项分成 14 个 \`family × form\` 组；每组只用第一项确定两个 C 常数，剩余所有样本作为**留出集**核对。
- **612 / 612 个独立留出条目，两个数组的预测值均逐字节精确一致；全部 626 项模型计算与原始双数组一致。**
- 4 个变体组只有 1 个原始样本，属于“单样本拟合、无独立验证”，不得宣称该 4 组的模型被外部样本验证。

14 个组含普通形态、\`_nh\`、\`00_51_00\`、\`11_00_00\`、\`12_00_00\`、\`11_00_00_nh\`、\`13_00_00\`，并分别覆盖常规和 \`uni\`。

完整审计结果：
- [626 项原生键和 Source OID 的原值/预测值](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M27/m27_626_native_icon_hash31_template_validation.csv)
- [14 组的拟合常量与独立样本数](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M27/m27_hash31_candidate_family_constants.json)

## 4. 扩大候选搜索到 140,000 组没有发现额外图标

对 14 个变体组中的每组 \`0000–9999\` 全部编号执行假设 Hash 计算，共 **140,000 组候选**，随后在完整的 **3543 对原始 u32** 中做精确查询。

| 对账项目 | 数量 |
| --- | ---: |
| 生成的数字/变体组合 | 140,000 |
| 至少命中第一个原生键数组 | 626 |
| 键与 Source OID 两项**同时**命中 | 626 |
| 命中但不属于 M25 的 628 个已确认主表 Source OID | **0** |
| 仅键命中、值不匹配 | 0 |

这意味着：**在此已经完全解析的 KIDS 类型双数组和已见 14 种名称模板范围内，没有发现其它数字编号图标**。它进一步支持 M26 对剩余 62 张参考头像的“本索引无可靠来源”结论。

但不能扩大成“2.0.1 整个游戏没有另外 62 张图像”：未覆盖其它类、纹理命名模式、缺失原始 FDATA 或不同版本。

[140,000 次候选中实际命中的 626 行证据](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M27/m27_10k_per_variant_reverse_numeric_probes.csv) · [M27 JSON 结果](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M27/m27_original_reverse31_model_summary.json)

## 5. 仍未完成的原生确认

**尚未证实原生软件如何计算 Hash**：目前为对大样本原始字节的精确数学拟合，尚未从 \`main\` 指令中定位该 \`hash31\` 的实现地址，也未证明目标文件名中反向数位来源。这也意味着常数 C 不能标记成已反推出的真实游戏字符串。

**尚未证实真正的物种 ID 消费者**：从 ExeFS \`main+0xDD1B48\` 确定了三项属性描述器，但还没有取得游戏自身从 species/villager ID 到此对象 key、再根据 key 查 Source OID 的完整调用链。M26 的 9 张歧义特别形态依旧只有图像优选，没有游戏运行时验明的最终形态。

**尚未恢复 62 张参考头像**：数字模板扫描没有额外原生 Source OID，这是一项有范围限制的负结果，不应宣称内容不存在或肯定属于 DLC。

## 6. 一键复现

\`\`\`bash
python -m Scripts.resources.m27_reverse_decimal_hash31 --self-test
python -m Scripts.resources.m27_reverse_decimal_hash31
\`\`\`

[GitHub Actions M27 完整源数据复验](https://github.com/969981/poko_resources/actions/runs/41995425771) 成功。它从原始 KIDSOBJDB 验证 SHA/3543 项数，再对照 M26/M25 原始数据，生成 CSV、常量和 JSON；任何来源 SHA 改变、数组偏移改变、预期 Source OID 不符或数学模型不符都会停止。

后续最短路线：在原始 NSO 中查找实际 31 倍递推／字节累加函数；从该函数的真实调用者回溯资源键输入，继而核验是否确实连接 KIDS \`0xE88C8D60\` 与 \`0x34CBB458\` 的并行索引。所有推测函数都要以原始机器码和上下文记录，不得直接升格为完整 runtime ID 映射。
