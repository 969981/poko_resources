# Pokopia 2.0.1 — 解包、验证和原始路径镜像发布

分支 `2.0.1_unpack`；原始输入路径 `2.0.1/`；唯一正式解包产物路径 `UnPack/2.0.1/`。

已实现 M0 输入盘点、M1 LINKDATA 全索引/解码、M2 RDB/RDX/FDATA 记录提取验证，并开始把**真正逐条解码的二进制文件**提交到 GitHub，而不再只上传报告。发布格式以 `2.0.1/romfs` 原始相对目录为准，按被解包的完整源文件名建立目录，按源文件存放 `decoded/` 和 `_manifest.csv`。分卷先恢复再处理。

## 核心入口

- [解包产物及格式](UnPack/2.0.1/README.md)
- [完整目录规则](docs/2.0.1/DIRECTORY.md)
- [总体计划与验收](docs/2.0.1/PLAN.md)
- [分阶段任务](docs/2.0.1/TASKS.md)
- [格式研究](docs/2.0.1/FORMATS.md)
- [GitHub 实际基线](docs/2.0.1/BASELINE.md)
- [M0/M1/M2 真实验证结果](docs/2.0.1/ROUND2_RESULTS.md)
- [Codex 目标模式](docs/2.0.1/CODEX_TARGET.md)

`Scripts/unpack/publish.py` 处理 LINKDATA/中小型 FDATA；`Scripts/unpack/publish_stream.py` 处理大型 FDATA 流式、分区解码与可拼合的超大记录。Actions 工作流为 `publish-unpack.yml`、`publish-unpack-phase2.yml`、`publish-unpack-large.yml`。

## 真实性、完整性与限制

- 元数据校验成功不代表已经上传资源；只把在分支上真实存在、带 SHA-256 的产物计入已发布。
- 不会把 `INDEXED`、`LOCATED`、`DECODE_FAILED`、`SKIPPED_BATCH_BUDGET` 与 `PUBLISHED` 混淆；具体见 `UnPack/2.0.1/_reports/`。
- 不改动原始 `2.0.1/`，保留 `exefs/main`，排除 `romfs/movie_asset/`；恢复的临时大容器不进入 Git。
- 超过 GitHub 100 MiB 单文件限制的解码结果应拆分为不超过 80 MiB 的顺序分段；独立 `.file` 仍须单独验证其语义格式。
