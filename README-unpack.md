# Pokopia 2.0.1 — Resource Unpacking & Analysis

> Branch: `2.0.1_unpack` · Source: `main` · Status: planning / no extractor has been validated here.

本分支用于研究 Pokopia v2.0.1 的资源索引、精确提取、结构解析与可复现验证。保留 `2.0.1/` 原始内容（含 `exefs/main`），不碰 `romfs/movie_asset/`。

## 分阶段目标

1. **M0：盘点/还原**：校验 7z 分卷、源文件哈希、容器来源、索引数和版本。
2. **M1：LINKDATA**：解析 `LI_C0_R.IDX`，对 `LD_C0_R.BIN` 做逐条定位、提取、解压、失败分类。
3. **M2：KT RDB**：解析 `root/system.rdb`、`root/system.rdx`，映射 FDATA、MountPoint、独立 .file，按条提取。
4. **M3：资源识别**：KIDSOBJDB、FlatBuffers/BFBS、文字和本地化等数据导出。
5. **M4：图形/地图**：模型、贴图、材质、地图、洞窟、建筑内部和场景关系的可验证还原。
6. **M5：工程化**：断点续跑、增量索引、回归测试、错误报告及有限资源上的批处理。

**优先顺序：M0→M1/M2→M3→M4；M5 从 M0 同步实施。**

## 阅读顺序

- [总体路线及验收](docs/2.0.1/PLAN.md)
- [细分任务 39 项](docs/2.0.1/TASKS.md)
- [GitHub 实际资源基线](docs/2.0.1/BASELINE.md)
- [目录/提交约定](docs/2.0.1/DIRECTORY.md)
- [格式研究记录](docs/2.0.1/FORMATS.md)
- [任务进度](docs/2.0.1/PROGRESS.md)
- [Codex 目标模式执行说明](docs/2.0.1/CODEX_TARGET.md)

## 边界

- 本次提交仅建立计划与研究目录，**没有宣称完成任何 ROM 解压或格式解码**。
- 原版游戏文件、超大中间产物、不确定授权的第三方代码不要追加到 Git 历史。
- 导出时每份资源应可通过 source path + source SHA-256 + index/record + byte offset/length 回溯。
- 对外报告必须分别统计：索引解析、容器定位、原始提取、解压成功、结构解析五个不同指标。
