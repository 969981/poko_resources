---
title: Obsidian 知识库维护规范
aliases: [Obsidian 管理说明, Pokopia 知识库维护]
tags: [pokopia, obsidian, documentation, workflow]
game_version: "2.0.1"
status: ACTIVE
updated: 2026-11-05
---
# 用 Obsidian 管理原生解包知识库

## Vault 的范围

建议把**整个 `poko_resources` 仓库根目录**作为 Vault，而不是仅把 `Technical/` 作为 Vault。这样可以在笔记中同时打开其他 `docs/2.0.1`、`Scripts` 及 `UnPack` 的 Markdown。主入口：[[README|Pokopia 2.0.1 技术知识库]]。

```powershell
git clone --recurse-submodules -b 2.0.1_unpack https://github.com/969981/poko_resources.git
cd poko_resources
git pull origin 2.0.1_unpack
```

在 Obsidian 选择“Open folder as vault”并选 `poko_resources`。无需额外社区插件即可使用 Wiki 双向链接、标签、反向链接和 Graph View。不要把个人 `.obsidian/` 插件/工作区状态当作研究源数据提交；若团队未来需要共享 Vault 配置，另行评审后只提交必要项。

## 推荐的笔记分类

| 内容 | 存放位置 | 编写要求 |
| --- | --- | --- |
| 经验证的格式结构、通用工具 | `docs/2.0.1/Technical/` | 尽量稳定，给出源代码链接、样本路径 |
| 每次 M0–M22 研究过程和反证 | `docs/2.0.1/M*.md` | 保持时间顺序，不因新发现删除历史 |
| 实际生成的二进制/PNG/CSV/SQLite | `UnPack/2.0.1/` 或 `_meta/` | 有 manifest、SHA，按仓库已有发布规则 |
| 直接可执行的提取/审计实现 | `Scripts/`、`Pokopia.Binary*` | 参数及依赖以代码为准 |
| 某一资源的新发现/调查 | 新的专题 Markdown | 复制 [[09-Research-Template]]，记录反例和证据等级 |

## 建议在专题笔记使用的 Frontmatter

```yaml
---
title: G1T 0x18 布局核验
aliases: [G1T Ounce Layout]
tags: [pokopia, texture, evidence]
game_version: "2.0.1"
status: PARTIAL
evidence_grade: E3
source_path: UnPack/2.0.1/romfs/motor_asset_re/KIDS_PLATFORM_OUNCE/0x00011c54.fdata/native/root_038147_a0ce9914.g1t
updated: 2026-11-05
---
```

`status` 建议限定 `VERIFIED`、`PARTIAL`、`UNKNOWN`、`DISPROVED`；`evidence_grade` 参阅 [[08-Evidence-And-Open-Questions]]。标记的是**本条结论**，不是整份文件全部语义均已验证。

## 链接规范

- 同目录笔记用 `[[04-Texture-Pipeline]]`（Obsidian）或 `[纹理](04-Texture-Pipeline.md)`（GitHub）；重要入口可保留这两种导航。
- 源代码和原始账本优先用**相对于当前 Markdown**的普通链接，例如 `[解包工具](../../../Scripts/README.md)`，GitHub 可直接点击。
- 原始 `*.bin`、`*.g1t` 没有必要插入整个文件到笔记；记录路径、Hash、条目号、偏移和少量允许公开的样例即可。
- 避免相同文件名产生歧义；新增专题采用唯一文件名，如 `G1T-Ounce-UV-20261105.md`。
- 不引用不稳定的绝对 Windows 盘符路径、个人用户名、凭据或私人目录。

## 一次研究完成后的提交标准

1. 运行脚本并保存命令、输入 SHA、输出 manifest/JSON 和失败案例。
2. 分清 `SOURCE_EXISTS`、`PNG_DECODED`、`NATIVE_ID_VERIFIED`、`GAME_VISIBLE_VERIFIED` 等不同层次。
3. 如果研究推翻旧判断：保留历史报告，在新笔记写清“反证”和被替代的结论。
4. 更新本文首页或对应专题索引，使新增文件可从 Obsidian 双向导航到达。
5. 提交后从 GitHub 打开 Markdown 检查相对链接；不将手动摆放的个人工作区布局作为验收条件。

导航：[[10-Toolchain-And-Dependencies]] · [[11-Format-Details]] · [[12-Reproducible-Recipes]] · [[13-Resource-Provenance-Map]] · [[14-Troubleshooting-And-Validation]]。
