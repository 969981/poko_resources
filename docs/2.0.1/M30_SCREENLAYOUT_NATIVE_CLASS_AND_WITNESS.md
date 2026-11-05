# M30 — ScreenLayout 原生类型名恢复与同一实体身份取证

> Pokémon Pokopia **2.0.1** · 分支 \`2.0.1_unpack\` · 截至本轮为止的头像数量：**307 张有原生图像与视觉高置信对应、9 张多候选、62 张未定位**。  
> **正式游戏运行时物种/村民 ID 绑定仍为 0**。本轮真正完成的是原始字段命名、两个 ScreenLayout 类注册链，以及可验证但尚未实际运行的 GDB 证据工具。

相关笔记：[[M29_NATIVE_IDENTITY_CALLER_AND_RUNTIME_PROOF]] · [[M28_ORIGINAL_HASH31_CONSUMER_AND_LOOKUP]] · [[M27_ORIGINAL_KIDS_REVERSE31_NUMERIC_HASH]] · [[M26_VILLAGER_ROSTER_AND_KIDS_PARALLEL_ARRAYS]] · [[M25_NATIVE_POKEMON_ICON_REGISTRY]]。

## 1. 证据源和边界

- 游戏原始 ExeFS \`2.0.1/exefs/main\` SHA-256：\`8a8ce87b4edfce88c6260da5dd80d6cafc03a761eebc842d7a3476e353a8336f\`
- KIDS 原生源 \`root_019167_50ae86ef.kidsobjdb\` SHA-256：\`86f90b4c11da9bc2b3e28889a5090ff507f96ca713fe4fad1dd50f6f692d7541\`
- 原生类型 \`0x9D1AFA46\`，源对象 \`0xB4A1803B\`，分别有两个长度为 **3543** 的 u32 数组；
- 在 628 个已确认的图标 Source OID 中，626 项可被 M27 的 Hash31 数值模板精确预测；这仅是资源名/来源对象数学模型，不是游戏物种 ID 计算器。

### M30.2 原始字段名称真实恢复

M26.3 的 \`main+0xDD1B48\` 属性描述器包含三个 original data 指针：

| 属性 Hash | 原始初始化字符串指针 cell | 指向 rodata | 恢复的游戏原始字段名 |
| --- | --- | --- | --- |
| \`0x2F610FEA\` | \`main+0x3331810\` | \`main+0x27FB2C7\` | \`ScreenLayoutTexturePackObjectNameHash\` |
| \`0xE88C8D60\` | \`main+0x3331818\` | \`main+0x27B13C1\` | \`TexturePackKeyHashArray\` |
| \`0x34CBB458\` | \`main+0x3331820\` | \`main+0x27CFED6\` | \`TexturePackObjectHashArray\` |

所有字段名直接从原始 NSO 只读段以带 NUL 的 UTF-8 原字节读出。**这些指针是字段名字符串，不是 getter 函数指针**；不可将它们当作 C++ 间接代码回调。

这还给之前的两组 3543 项数据提供了**原始语义命名**：

\`\`\`text
TexturePackKeyHashArray    : 3543 × u32 (原始 KIDS 数据偏移 364556)
TexturePackObjectHashArray : 3543 × u32 (原始 KIDS 数据偏移 378728)
\`\`\`

**不能**因此把某个 Key 当作国图编号、物种 ID 或游戏村民 ID。

[三个属性原始字节和指针表](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M30/m30_2_original_KIDS_field_descriptor_labels.json)

## 2. M30.3：ScreenLayout / TexturePack 词汇和可执行代码来源

从原始 NSO 的 \`rodata\` 中识别到 **48 条**包含 \`ScreenLayout\` 或 \`TexturePack\` 的字符串，得到 **31 处**原始相邻 \`ADRP+ADD\` 字符串引用。Hash 原始常量三项都坐落于 \`main+0x2838834–0x283883C\`。在限定 \`MOVZ low16 → MOVK high16\` 的固定指令模板下，没有找到可证明的 Hash 构造点。

优先结构名：

- \`ScreenLayoutTexturePackSettings\`
- \`StaticScreenLayoutTextures\`
- \`StaticScreenLayoutTexInfoFile\`
- \`TexturePackAssetKeyHashArray\`
- \`TexturePackObjectKeyHashArray\`
- \`TexturePackSettingsObjectHashArray\`

[ScreenLayout/TexPack 词汇及 31 处原始引用](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M30/m30_3_original_texture_pack_vocabulary_xrefs.json)

## 3. M30.4 / M30.5：两个已恢复的类型 Hash 在源代码中正式绑定到原始名称

这是本阶段最重要的原生静态代码突破。

### \`ScreenLayoutTexturePackSettings\` → \`0x9D1AFA46\`

\`\`\`asm
main+0xBAA51C  adrp x1, #0x27B0000
main+0xBAA520  add  x1, x1, #0x9B9    ; x1 = ScreenLayoutTexturePackSettings
main+0xBAA524  mov  x0, x19
main+0xBAA528  bl   #0xBE19B4       ; 原始类型初始化
...
main+0xBE19C8  mov w1, #0xFA46
main+0xBE19D0  movk w1, #0x9D1A, lsl #16
\`\`\`

\`main+0x349C2E0\` 初始化为 BSS 类对象 \`main+0x367AD40\`，\`main+0x349C2E8\` 指向安装到 \`main+0x33135C8\` 的方法表。其 \`vtable+0x18\` 关联属性枚举 \`main+0xDD1B48\`。由这条证据链将三项真实属性名与游戏原始类型名连接。

### \`StaticScreenLayoutTextures\` → \`0x79991E79\`

\`\`\`asm
main+0xBA6A10  adrp x1, #0x279B000
main+0xBA6A14  add  x1, x1, #0x44D    ; x1 = StaticScreenLayoutTextures
main+0xBA6A18  mov  x0, x19
main+0xBA6A1C  bl   #0xBB8558        ; 原始类型初始化
...
main+0xBB85F8  mov  w1, #0x1E79
main+0xBB8600  movk w1, #0x7999, lsl #16
\`\`\`

这一类型原始 BSS 对象地址 \`main+0x366E6F0\`，方法表 \`main+0x32F0EE0\`，\`vtable+0x18\` 指向 \`main+0xCE854C\`。M19–M24 已验证的 \`0x2856A1B3\` 类型属性由原始 KIDS Source OID 指向 Texture OID。

这使得旧的两个“未知类 Hash”取得对应的**原生 ScreenLayout 类型名**：

| 原始游戏类型名 | Type Hash | 已确认本地结构 |
| --- | --- | --- |
| \`ScreenLayoutTexturePackSettings\` | \`0x9D1AFA46\` | TexturePack Key Hash / Object Hash 的 3543 项并行数组 |
| \`StaticScreenLayoutTextures\` | \`0x79991E79\` | Source OID → Texture OID 的原生纹理对象引用 |

两者属于同一广义 ScreenLayout 静态资源注册体系。**不意味着它们使用同一个运行时 Pokémon 实例，也不意味着已证明二者的查询函数之间的动态调用边。** 此处 \`x19\` 应视为注册上下文参数，不能直接认定为 Pokémon 指针。

[五个 ScreenLayout 参考点的原生代码窗口](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M30/m30_4_screen_layout_texture_consumer_windows.json)  
[两个正式类型名、BL 指令、类型 Hash 与安装方法表的交叉证据](../../UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M30/m30_5_two_named_KIDS_class_registrations.json)

## 4. M30.0 / M30.1：如何取得“同一对象”运行时证据，而不制造假映射

新增两个**源码级可用但未接入实际模拟器**的工具：

- \`Scripts/gdb/m30_pokopia_two_phase_witness.py\`：GDB 原生 AArch64 只读采样，两种模式各只设置两个**请求的硬件断点**；
- \`Scripts/resources/m30_1_review_original_runtime_witness.py\`：离线原始 ROMFS 校验器，含模拟数据正反例。

### 身份／列表阶段

\`\`\`gdb
source Scripts/gdb/m30_pokopia_two_phase_witness.py
pokopia-m30-start 0xACTUAL_MAIN_BASE identity 100 m30_identity.jsonl
continue
\`\`\`

\`0xACTUAL_MAIN_BASE\` 须由实际连接的 **2.0.1 游戏进程**获取，不能把以上字面文字直接运行。可在 GDB 暂停后使用：

\`\`\`gdb
pokopia-m30-mark icon_variant_A
continue
\`\`\`

要停止时，在 GDB 可用的暂停状态执行：

\`\`\`gdb
pokopia-m30-stop
\`\`\`

这一阶段仅对两个**原生静态源字节确认的加载点**采样：

- \`main+0x1136A60\`：记录 \`x22+4…+9\` 六个原生字节（对应三个 16 位值）；
- \`main+0x5FD168\`：记录 \`x19+0x26\` 的单字节标志。

它们是原始指令所使用的字段地址，但字段业务语义尚需继续沿真实消费者验证。**场景标记只是用户操作标签，不是同实例身份的证据。**

### KIDS 属性阶段

\`\`\`gdb
pokopia-m30-start 0xACTUAL_MAIN_BASE kids 100 m30_kids.jsonl
continue
\`\`\`

- \`main+0xDD1B48\`：采集 KIDS 属性描述器入口的寄存器及索引；
- \`main+0xDD1B74\`：原始指令为 \`ldr w12,[x9,w3,sxtw #2]\`，从相应内存地址读取**属性描述器 Hash**；当 \`w3=0/1/2\`，核对三个已验证 Hash。

两阶段各读取断点位置的原始 AArch64 指令字（4 字节），与固定原始指令值对账：

| 原生断点 | 期待的原始指令字 |
| --- | --- |
| \`main+0x1136A60\` | \`0x794012C8\` |
| \`main+0x5FD168\` | \`0x912CD463\` |
| \`main+0xDD1B48\` | \`0x2A1F03E8\` |
| \`main+0xDD1B74\` | \`0xB863D92C\` |

**四条指令 spot-check 不证明完整游戏 Build ID**。硬件断点是否被实际使用的模拟器 GDB Stub 支持也尚未测试；该工具没有被宣称已通过实际断点运行。断点会带来执行暂停、调度开销，但此工具没有主动写游戏数据。

### 已确认真实原始 KIDS 槽位时的可选原始值对账

仅在**另一条已证明的运行时查询代码**提供可靠的 key 地址、Source OID 地址和数组槽位时，才可在目标暂停时提交：

\`\`\`gdb
pokopia-m30-pair 455 0xACTUAL_KEY_ADDRESS 0xACTUAL_SOURCE_ADDRESS
\`\`\`

此命令会读取两处操作员提供的 u32 地址。校验器会与 SHA256 固定的原始 KIDS 双数组对应槽位逐项比较，**但即使两个值一致，也仅表示字节值与原始资源数据一致**，不会自动认定这些地址属于当前角色对象。

原始第 455 槽示例：

\`\`\`text
KIDS Key Hash = 0x469E2C00
Source OID    = 0x06AB845F
Texture OID   = 0xC1A6D60C  (已经另有原始 KIDS 来源)
\`\`\`

### 离线校验

\`\`\`powershell
python -m Scripts.resources.m30_1_review_original_runtime_witness --self-test
python -m Scripts.resources.m30_1_review_original_runtime_witness --input m30_identity.jsonl --out m30_identity_review
python -m Scripts.resources.m30_1_review_original_runtime_witness --input m30_kids.jsonl --out m30_kids_review
\`\`\`

校验器会拒绝错误 PC、错误源字节、错误描述器值、缺少原始内存地址依据或伪造的 \`game_species_ID_verified\`。允许操作员提供原始候选地址，但会**永久保持** \`operator_supplied_address_provenance=False\`，不能把一个静态表匹配伪装成同实体调用链。

**重要：分两阶段取得的记录，即使场景名相同、出现同一个十六进制数字或同一线程，也不能证明它们属于同一个游戏实体。** 真正的下一步必须定位游戏运行时代码如何从实际实体实例取 \`species/form\`，怎样调用 ScreenLayout 资源索引，进而使用相同 KIDS Key 返回 Source OID。

## 5. 确认身份需要的最小完整证据

必须在同一次可重复的游戏对象操作中确认：

1. **游戏对象和 ID 来源**：原生分配/加载代码及结构偏移证明物种 ID、形态字段，记录实际对象指针；
2. **资源选择调用**：原生读取该 ID/形态数据、向某个查询函数传参，有真实指令和调用上下文；
3. **纹理包 Key 查询**：函数实际访问本类型的 \`TexturePackKeyHashArray\` / \`TexturePackObjectHashArray\`，命中具体数组索引；
4. **Texture OID 链接**：查询得到的 Source OID 与原始 \`StaticScreenLayoutTextures\` 的 Texture OID 引用相同，并连接原生 G1T/TEXINFO、PNG；
5. **第二个形态反例**：同物种不同形态或同场景不同实体能够独立重复、区分错误的视觉最优映射；
6. **不篡改正式数据库**：每条对应关系须单独保留内存快照、原始指令地址、原始 KIDS 字节和版本证据。未齐备不得标为正式 native game ID。

## 6. CI 来源与当前完成度

| 工作流 | 已验证 | 未验证 |
| --- | --- | --- |
| [M30 原始读值/取证工具](https://github.com/969981/poko_resources/actions/runs/42012291555) | 4 个原生指令字、3543 对原始数组、Python 语法和模拟 JSONL 反例 | 实机/模拟器断点 |
| [M30.2 字段名恢复](https://github.com/969981/poko_resources/actions/runs/42012601117) | 3 个 UTF-8 NUL 源字符串与原生指针 | 字段运行时消费者 |
| [M30.3 纹理包词汇与引用](https://github.com/969981/poko_resources/actions/runs/42013105800) | 48 源字符串、31 处 ADRP+ADD | 真实游戏物种 ID |
| [M30.4 ScreenLayout 函数窗口](https://github.com/969981/poko_resources/actions/runs/42013523047) | 5 个地址及 59 条局部 BL 源代码 | 真正纹理选择调用 |
| [M30.5 两个原始类型名](https://github.com/969981/poko_resources/actions/runs/42014165740) | 类型注册 BL、原始 class Hash、BSS/vtable、2 个原生类型名 | 动态同实体身份绑定 |

所有工作流均成功，源报告提交于 \`UnPack/2.0.1/Resources/Villagers/Native_2.0.1/M30/\`。M30 动态 GDB 取证工具和验证器已经准备好，**未制造任何“真实游戏运行”采样结果**。

### 总结

KIDS 的**ScreenLayout 静态类型与字段命名**已推进到真正的源代码注册关系。下一步不该继续猜 \`0043\` 是否图鉴号，而要找到**谁实际调用 TexturePack Key→Object 查询**及该调用上游是否从运行时 Pokémon 实例读取物种和形态；取得同对象证据前，头像统计仍为 **307 / 9 / 62**，正式 ID 绑定为 **0**。
