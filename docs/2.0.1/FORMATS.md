# 格式研究与证据等级

| 格式/容器 | 输入样本路径 | 研究方向 | 当前状态 |
|---|---|---|---|
| 7z 分卷 | `LD_C0_R.BIN.7z.001`、`*.fdata.7z.001` | 连续性、7z test、解压大小 | 仅确认存在，未执行验证 |
| LINKDATA IDX | `LI_C0_R.IDX` | record 结构、endian、flags、offset | 未在本分支实测 |
| LINKDATA BIN | `LD_C0_R.BIN`（还原后） | block 映射、codec、提取 | 未实测 |
| KT root RDB/RDX | `root.rdb` / `root.rdx` | records、FDATA hash、MountPoint | 有历史离线索引审计，待重验 |
| KT system RDB/RDX | `system.rdb` / `system.rdx` | system 资源及分区映射 | 路径已确认，待解析 |
| FDATA | `0x2943e4da.fdata` 等 | byte range、压缩数据 | 待实测 |
| 独立 FILE | `data/0x9d464c3c.file` 等 | 直接定位、特殊 flags | 待实测 |
| KIDSOBJDB | `b290631c` 等候选 | 对象、成员、字段、引用 | 尚未验证结构 |
| BFBS/FlatBuffers | 待按签名及 ExeFS 交叉索引 | schema、表、对象关系 | 候选方向 |
| 贴图/模型/地图 | 待提取候选 | 转换、材质、场景位置 | 未实测 |

### 待研究开源工具

- [RDBExplorer](https://github.com/MrIkso/RDBExplorer)
- [fdata_dump](https://github.com/DeathChaos25/fdata_dump)
- [Cethleann](https://github.com/neptuwunium/Cethleann)
- [yumia_fdata_tools](https://github.com/eArmada8/yumia_fdata_tools)

这些只作为参考，未经实测不得断言完全兼容 Pokopia 2.0.1。第三方工具版本/commit、许可证、使用参数和实际测试结果单独留档；不能直接把不同游戏的格式假设照搬。

### 证据等级

- **E0** 仅命名/扩展名猜测；
- **E1** 原始文件存在且 SHA/size 已记录；
- **E2** IDX/RDB 字段解析可通过边界与样本；
- **E3** 原始数据可字节级提取、编码识别；
- **E4** 格式内容/字段有真实双向测试；
- **E5** 可复现转换或渲染，附对照和依赖清单。
